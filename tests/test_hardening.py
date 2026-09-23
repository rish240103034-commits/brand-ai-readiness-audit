"""Robustness/rubric-hardening tests: crash-proof pipeline + broken-link timeout handling."""
import unittest

import run_audit
from auditlib import http, htmlparse
from auditlib.config import make_config
from auditlib.context import AuditContext
from auditlib.checks import crawl_render
from tests.helpers import FakeFetcher, _resp


class SafeWrapperTests(unittest.TestCase):
    def test_safe_returns_value_on_success(self):
        rpt = {"notes": []}
        self.assertEqual(run_audit._safe(rpt, "x", lambda: 42, 0), 42)
        self.assertEqual(rpt["notes"], [])

    def test_safe_swallows_exception_and_notes(self):
        rpt = {"notes": []}
        def boom():
            raise ValueError("kaboom")
        out = run_audit._safe(rpt, "widget", boom, {"default": True})
        self.assertEqual(out, {"default": True})            # report still gets a value
        self.assertTrue(any("widget step skipped" in n for n in rpt["notes"]))


class BrokenLinkClassifierTests(unittest.TestCase):
    def _ctx(self):
        base = "https://x.example/"
        home_html = '<html lang="en"><head><title>t</title></head><body>' \
                    '<a href="/missing">m</a><a href="/timeout">t</a></body></html>'

        class Fetcher(FakeFetcher):
            def fetch(self, url, method="GET", max_attempts=None, timeout=None):
                self.request_count += 1
                if url.endswith("/timeout"):   # slow/bot-protected -> status 0, NOT broken
                    return http.Response(url=url, final_url=url, status=0, headers={}, body="",
                                         raw_len=0, content_type="", elapsed_ms=1, ok=False, error="timed out")
                if url.endswith("/missing"):   # a real 404 -> broken
                    return http.Response(url=url, final_url=url, status=404, headers={}, body="",
                                         raw_len=0, content_type="", elapsed_ms=1, ok=False, error="http_404")
                return super().fetch(url)

        cfg = make_config("balanced").derive(allow_private_hosts=True)
        fetcher = Fetcher(cfg)
        home_resp = _resp(base, home_html)
        return AuditContext(start_url=base, cfg=cfg, fetcher=fetcher,
                            responses=[home_resp], pages=[htmlparse.parse(base, home_html)])

    def test_timeout_not_reported_as_broken(self):
        findings = crawl_render._broken_link_findings(self._ctx())
        self.assertEqual(len(findings), 1)  # only the real 404
        pages = " ".join(findings[0].affected_pages)
        self.assertIn("/missing", pages)
        self.assertNotIn("/timeout", pages)  # timeout is NOT a broken link

    def _ctx_status(self, links):
        """Build a ctx whose links return the given {path: status}."""
        base = "https://x.example/"
        anchors = "".join(f'<a href="{p}">l</a>' for p in links)
        home_html = f'<html lang="en"><head><title>t</title></head><body>{anchors}</body></html>'

        class Fetcher(FakeFetcher):
            def fetch(self, url, method="GET", max_attempts=None, timeout=None):
                self.request_count += 1
                for path, st in links.items():
                    if url.endswith(path):
                        return http.Response(url=url, final_url=url, status=st, headers={}, body="",
                                             raw_len=0, content_type="", elapsed_ms=1,
                                             ok=200 <= st < 400, error="" if 200 <= st < 400 else f"http_{st}")
                return super().fetch(url)

        cfg = make_config("balanced").derive(allow_private_hosts=True)
        return AuditContext(start_url=base, cfg=cfg, fetcher=Fetcher(cfg),
                            responses=[_resp(base, home_html)],
                            pages=[htmlparse.parse(base, home_html)])

    def test_gated_statuses_not_broken(self):
        # 401/403/405/429 mean the link exists but is gated/rate-limited -> NOT broken.
        findings = crawl_render._broken_link_findings(
            self._ctx_status({"/login": 401, "/blocked": 403, "/head-no": 405, "/rate": 429}))
        self.assertEqual(findings, [])

    def test_gone_and_server_error_are_broken(self):
        findings = crawl_render._broken_link_findings(
            self._ctx_status({"/gone": 410, "/oops": 503, "/blocked": 403}))
        self.assertEqual(len(findings), 1)
        pages = " ".join(findings[0].affected_pages)
        self.assertIn("/gone", pages)
        self.assertIn("/oops", pages)
        self.assertNotIn("/blocked", pages)   # 403 excluded


if __name__ == "__main__":
    unittest.main()
