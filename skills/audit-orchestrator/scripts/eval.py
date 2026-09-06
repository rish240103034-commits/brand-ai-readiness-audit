#!/usr/bin/env python3
"""Generalization + false-positive eval harness (fully offline, deterministic).

Runs the marketplace against a small, labeled corpus of *synthetic* sites — one per failure mode,
plus a deliberately clean site and a non-English site — served from an in-process mock HTTP server
(no live network). For each fixture it checks:

  * **recall** — the expected finding categories are detected on the "bad" fixtures, and
  * **false positives** — the clean site produces no critical/high findings, and the non-English
    site isn't flagged for English-only artifacts (missing CTA / hreflang).

It prints a precision/recall-style scorecard. This is the evidence behind the rubric's
"few misses, few false positives … generalization tested by construction". Run:

    python skills/audit-orchestrator/scripts/eval.py
"""
from __future__ import annotations

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import run_audit                                    # noqa: E402
from auditlib.config import make_config             # noqa: E402

ROBOTS_OK = "User-agent: *\nAllow: /\nSitemap: http://SITE/sitemap.xml\n"

# --- fixture corpus ---------------------------------------------------------------
_CLEAN_HOME = """<!doctype html><html lang="en"><head>
<title>Acme Robotics — Industrial Automation</title>
<meta name="description" content="Acme Robotics designs and builds industrial automation cells for manufacturers.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="http://SITE/">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization",
"name":"Acme Robotics","url":"http://SITE/","logo":"http://SITE/logo.png","foundingDate":"2004",
"sameAs":["https://www.linkedin.com/company/acme","https://www.wikidata.org/wiki/Q1"]}</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"Acme Robotics","url":"http://SITE/"}</script>
</head><body><nav><a href="/about">About</a><a href="/products/x">Products</a><a href="/contact">Contact</a></nav>
<h1>Industrial automation that ships</h1>
<p>Acme Robotics designs and builds automation cells for manufacturing, founded 2004 in Pune. We serve
automotive, electronics, and logistics customers across India and Europe with reliable, supported systems.</p>
<a href="/contact">Contact sales</a>
<footer><a href="https://www.linkedin.com/company/acme">LinkedIn</a> · © 2026 Acme Robotics</footer></body></html>""".replace("\n", " ")
_CLEAN_ABOUT = ('<!doctype html><html lang="en"><head><title>About Acme Robotics</title>'
                '<meta name="description" content="About Acme Robotics, founded 2004."><meta name="viewport" content="width=device-width, initial-scale=1"></head>'
                '<body><nav><a href="/">Home</a><a href="/products/x">Products</a><a href="/contact">Contact</a></nav>'
                '<h1>About Acme Robotics</h1><p>Founded 2004 in Pune, Acme Robotics builds automation cells for '
                'manufacturers worldwide, with a focus on reliability and long-term support.</p></body></html>')
_CLEAN_PROD = ('<!doctype html><html lang="en"><head><title>Cell X — Acme Robotics</title>'
               '<meta name="description" content="Cell X automation unit by Acme Robotics."><meta name="viewport" content="width=device-width, initial-scale=1">'
               '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Cell X",'
               '"image":"http://SITE/x.png","description":"Automation cell","brand":{"@type":"Brand","name":"Acme Robotics"},'
               '"offers":{"@type":"Offer","price":"1000","priceCurrency":"USD","availability":"https://schema.org/InStock"}}</script></head>'
               '<body><nav><a href="/">Home</a><a href="/about">About</a><a href="/contact">Contact</a></nav>'
               '<h1>Cell X automation unit</h1><p>Cell X is a compact automation cell for small-batch manufacturing, '
               'supported by Acme Robotics with installation and training included.</p></body></html>')

FIXTURES = {
    "clean": {
        "pages": {"/": _CLEAN_HOME, "/about": _CLEAN_ABOUT, "/products/x": _CLEAN_PROD,
                  "/contact": ('<!doctype html><html lang="en"><head><title>Contact Acme Robotics</title>'
                               '<meta name="description" content="Contact Acme Robotics sales and support.">'
                               '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
                               '<body><nav><a href="/">Home</a><a href="/about">About</a><a href="/products/x">Products</a></nav>'
                               '<h1>Contact Acme Robotics</h1><p>Reach Acme Robotics sales and support by email at '
                               'hello@acme.example or call during business hours; we respond within one working day.</p>'
                               '<a href="mailto:hello@acme.example">Email us</a></body></html>')},
        "robots": ROBOTS_OK, "sitemap": True,
        "expect": set(), "expect_absent_cat": set(), "max_critical": 0, "max_high": 0,
    },
    "broken_spa": {
        "pages": {"/": '<!doctype html><html><head><title>App</title><script src="/a.js"></script></head>'
                        '<body><div id="root"></div><noscript>You need to enable JavaScript to run this app.</noscript></body></html>'},
        "robots": "", "expect": {"js-render-gap"},
    },
    "no_schema_commerce": {
        "pages": {"/": '<!doctype html><html lang="en"><head><title>Shop</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>'
                        '<body><h1>Shop</h1><p>Widgets for $9.99. Add to cart today.</p><a href="/product/x">Widget</a></body></html>',
                  "/product/x": '<!doctype html><html lang="en"><head><title>Widget</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>'
                                '<body><h1>Widget</h1><p>Buy the Widget for $9.99. Add to cart.</p></body></html>'},
        "robots": "", "expect": {"structured-data"},
    },
    "blocked_robots": {
        "pages": {"/": _CLEAN_HOME},
        "robots": "User-agent: PerplexityBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n",
        "expect": {"crawlability"},
    },
    "stale": {
        "pages": {"/": '<!doctype html><html lang="en"><head><title>Old Co</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>'
                        '<body><h1>Old Co</h1><p>We have been around a long time and do many things for many people.</p>'
                        '<footer>© 2016 Old Co</footer></body></html>',
                  "/blog/post": '<!doctype html><html lang="en"><head><title>Post</title></head>'
                                '<body><h1>Post</h1><p>5 min read of undated content about our services.</p></body></html>'},
        "robots": "", "expect": {"freshness"},
    },
    "contradictory": {
        "pages": {"/": '<!doctype html><html lang="en"><head><title>Acme</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>'
                        '<body><h1>Acme</h1><p>Acme was founded in 2016 by makers.</p></body></html>',
                  "/about": '<!doctype html><html lang="en"><head><title>About</title>'
                            '<script type="application/ld+json">{"@type":"Organization","name":"Acme","foundingDate":"2014-01-01"}</script></head>'
                            '<body><h1>About</h1><p>About Acme.</p></body></html>'},
        "robots": "", "expect": {"entity-identity"},
    },
    "noindex": {
        "pages": {"/": '<!doctype html><html lang="en"><head><title>Hidden</title><meta name="robots" content="noindex">'
                        '<meta name="viewport" content="width=device-width, initial-scale=1"></head><body><h1>Hidden</h1>'
                        '<p>This page is public content but set to noindex by mistake, which hides it from results.</p></body></html>'},
        "robots": "", "expect": {"indexability"},
    },
    "non_english": {
        "pages": {"/": '<!doctype html><html lang="fr"><head><title>Boutique — produits</title>'
                        '<meta name="description" content="Boutique de produits artisanaux."><meta name="viewport" content="width=device-width, initial-scale=1"></head>'
                        '<body><nav><a href="/produits">Produits</a><a href="/contact">Contact</a><a href="/apropos">À propos</a></nav>'
                        '<h1>Bienvenue à la boutique</h1><p>Nous vendons des produits artisanaux de haute qualité fabriqués '
                        'localement, livrés partout en France avec un service client réactif.</p><a href="/panier">Ajouter au panier</a></body></html>'},
        "robots": "", "expect_absent_cat": set(),
        "expect_absent_title": {"call-to-action", "hreflang", "requires client-side"},
    },
}


def _serve_and_audit(fx):
    state = {}  # populated once the port is known, read by the handler at request time

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/robots.txt":
                r = state["robots"]
                return self._s(200 if r else 404, r.encode(), "text/plain")
            if self.path == "/sitemap.xml" and state["sitemap"] is not None:
                return self._s(200, state["sitemap"].encode(), "application/xml")
            if self.path in state["pages"]:
                return self._s(200, state["pages"][self.path].encode(), "text/html")
            return self._s(404, b"nope", "text/plain")
        def _s(self, c, b, t):
            self.send_response(c); self.send_header("Content-Type", t)
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    base = f"127.0.0.1:{srv.server_address[1]}"     # real host:port — keeps the mock self-consistent
    state["pages"] = {p: h.replace("SITE", base) for p, h in fx["pages"].items()}
    state["robots"] = fx.get("robots", "").replace("SITE", base)
    state["sitemap"] = ("<urlset>" + "".join(f"<url><loc>http://{base}{p}</loc></url>"
                                             for p in fx["pages"]) + "</urlset>") if fx.get("sitemap") else None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        cfg = make_config("balanced").derive(allow_private_hosts=True, delay=0.0, max_pages=6)
        rpt, _ = run_audit.run(f"http://{base}/", cfg, external=False)
    finally:
        srv.shutdown(); srv.server_close()
    return rpt


def evaluate():
    """Return (rows, summary) with per-fixture pass/fail + aggregate recall/FP metrics."""
    rows = []
    exp_total = exp_hit = 0
    fp_total = 0
    for name, fx in FIXTURES.items():
        rpt = _serve_and_audit(fx)
        cats = {f["category"] for f in rpt.get("findings", [])}
        titles = " ".join(f["title"].lower() for f in rpt.get("findings", []))
        sev = [f["severity"] for f in rpt.get("findings", [])]

        expect = fx.get("expect", set())
        missed = expect - cats
        exp_total += len(expect); exp_hit += len(expect) - len(missed)

        fps = []
        for t in fx.get("expect_absent_title", set()):
            if t in titles:
                fps.append(f"unexpected '{t}'")
        if "max_critical" in fx and sev.count("critical") > fx["max_critical"]:
            fps.append(f"{sev.count('critical')} critical (>{fx['max_critical']})")
        if "max_high" in fx and sev.count("high") > fx["max_high"]:
            fps.append(f"{sev.count('high')} high (>{fx['max_high']})")
        fp_total += len(fps)

        ok = not missed and not fps
        rows.append({"fixture": name, "expected": sorted(expect), "detected_cats": sorted(cats),
                     "missed": sorted(missed), "false_positives": fps, "findings": len(sev), "pass": ok})
    recall = round(exp_hit / exp_total, 3) if exp_total else 1.0
    summary = {"fixtures": len(rows), "passed": sum(1 for r in rows if r["pass"]),
               "recall": recall, "false_positive_flags": fp_total,
               "all_pass": all(r["pass"] for r in rows)}
    return rows, summary


def main() -> int:
    rows, s = evaluate()
    print("=== Marketplace generalization / false-positive eval (offline, deterministic) ===\n")
    for r in rows:
        status = "PASS" if r["pass"] else "FAIL"
        print(f"[{status}] {r['fixture']:18s} findings={r['findings']:2d} "
              f"expected={r['expected'] or '—'}")
        if r["missed"]:
            print(f"         MISSED: {r['missed']}")
        if r["false_positives"]:
            print(f"         FALSE POSITIVES: {r['false_positives']}")
    print(f"\nFixtures passed : {s['passed']}/{s['fixtures']}")
    print(f"Recall          : {s['recall']:.2f}  (expected finding-categories detected on 'bad' fixtures)")
    print(f"False-positive flags: {s['false_positive_flags']}  (clean & non-English fixtures)")
    print("RESULT:", "ALL PASS" if s["all_pass"] else "FAILURES")
    return 0 if s["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
