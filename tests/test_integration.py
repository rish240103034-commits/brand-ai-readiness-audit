"""End-to-end integration test: run the full orchestrator against a local mock HTTP server.

Exercises the real crawl → parse → all checks → score → schema pipeline with zero external
network access (the server runs on 127.0.0.1 in a background thread).
"""
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import run_audit
from auditlib import report as R
from auditlib.config import make_config

# A deliberately imperfect site: no structured data, no viewport, missing meta description.
HOME = b"""<!doctype html><html><head><title>MockCo</title></head>
<body><h1>MockCo</h1><p>We sell things. Contact us to learn more about MockCo products today.</p>
<a href="/about">About</a><a href="/products">Products</a></body></html>"""
ABOUT = b"""<!doctype html><html><head><title>About MockCo</title></head>
<body><h1>About</h1><p>MockCo was founded a while ago and does business worldwide.</p>
<a href="/">Home</a></body></html>"""
PRODUCTS = b"""<!doctype html><html><head><title>Products</title></head>
<body><h1>Products</h1><p>Our catalog.</p><a href="/">Home</a></body></html>"""

ROUTES = {"/": HOME, "/about": ABOUT, "/products": PRODUCTS}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_GET(self):
        if self.path == "/robots.txt":
            body = b"User-agent: *\nAllow: /\n"
            self._send(200, body, "text/plain")
        elif self.path in ROUTES:
            self._send(200, ROUTES[self.path], "text/html")
        else:
            self._send(404, b"not found", "text/plain")

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _run(self, **overrides):
        cfg = make_config("balanced").derive(
            allow_private_hosts=True, max_pages=5, delay=0.0, **overrides)
        url = f"http://127.0.0.1:{self.port}/"
        return run_audit.run(url, cfg, external=True)

    def test_full_pipeline_produces_valid_scored_report(self):
        rpt, code = self._run()
        self.assertEqual(code, run_audit.EXIT_OK)
        self.assertEqual(R.validate(rpt), [])
        self.assertGreaterEqual(rpt["pages_crawled"], 2)
        self.assertIn("score", rpt)
        self.assertIn(rpt["score"]["grade"], list("ABCDF"))
        self.assertEqual(len(rpt["skills_run"]), 5)

    def test_expected_findings_present(self):
        rpt, _ = self._run()
        titles = {f["title"] for f in rpt["findings"]}
        self.assertIn("No structured data anywhere in the sampled pages", titles)
        self.assertIn("No responsive viewport meta tag", titles)
        # findings are prioritized and ided
        self.assertEqual(rpt["findings"][0]["id"], "F-001")
        self.assertEqual(rpt["findings"][0]["priority"], 1)

    def test_skills_subset(self):
        cfg = make_config("balanced").derive(allow_private_hosts=True, max_pages=3, delay=0.0)
        url = f"http://127.0.0.1:{self.port}/"
        rpt, _ = run_audit.run(url, cfg, external=True, only_skills=["engagement-audit"])
        self.assertEqual(rpt["skills_run"], ["engagement-audit"])
        self.assertTrue(all(f["dimension"] == "engagement" for f in rpt["findings"]))


if __name__ == "__main__":
    unittest.main()
