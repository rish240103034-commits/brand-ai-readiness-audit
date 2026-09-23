"""Tests for regional 'branch' detection (India/Global/…) and the opt-in per-region audit."""
import unittest

from auditlib import regions
from tests.helpers import make_ctx, GOOD_HOME

MULTI = ('<!doctype html><html lang="en"><head><title>Acme Global</title>'
         '<link rel="alternate" hreflang="x-default" href="https://acme.example/">'
         '<link rel="alternate" hreflang="en-in" href="https://acme.example/in/">'
         '<link rel="alternate" hreflang="en-gb" href="https://acme.example/uk/">'
         '</head><body><h1>Acme</h1></body></html>')
INDIA = ('<!doctype html><html lang="en-IN"><head><title>Acme India</title>'
         '<link rel="alternate" hreflang="x-default" href="https://acme.example/">'
         '<link rel="alternate" hreflang="en-in" href="https://acme.example/in/">'
         '</head><body><h1>Acme India</h1></body></html>')


def by_region(block):
    return {v["region"]: v for v in block["variants"]}


class RegionDetectionTests(unittest.TestCase):
    def test_detects_variants_and_labels(self):
        block, _ = regions.scan(make_ctx([("https://acme.example/", MULTI),
                                          ("https://acme.example/in/", INDIA)]))
        r = by_region(block)
        self.assertIn("India", r)
        self.assertIn("Global (x-default)", r)
        self.assertEqual(r["India"]["locale"], "en-in")
        self.assertTrue(r["Global (x-default)"]["is_default"])

    def test_dead_variant_flagged(self):
        # /uk/ is declared but NOT in the sample → probe hits FakeFetcher 404 → dead + high finding
        block, findings = regions.scan(make_ctx([("https://acme.example/", MULTI),
                                                 ("https://acme.example/in/", INDIA)]))
        uk = by_region(block)["United Kingdom"]
        self.assertEqual(uk["reachable"], "error")
        self.assertEqual(uk["status"], 404)
        self.assertTrue(any("unreachable" in f.title.lower() for f in findings))

    def test_single_region_site_is_empty(self):
        block, findings = regions.scan(make_ctx([("https://acme.example/", GOOD_HOME)]))
        self.assertEqual(block["count"], 0)
        self.assertEqual(findings, [])

    def test_reciprocity_marked_for_cluster(self):
        block, _ = regions.scan(make_ctx([("https://acme.example/", MULTI),
                                         ("https://acme.example/in/", INDIA)]))
        self.assertTrue(all(v["reciprocal"] for v in block["variants"]
                            if "hreflang" in v["declared_via"]))


def _many_home(n):
    links = "".join(
        f'<link rel="alternate" hreflang="en-{c}" href="https://acme.example/{c}/en/">'
        for c in [f"r{i:02d}" for i in range(n)])
    return f'<!doctype html><html lang="en"><head><title>Acme</title>{links}</head><body>x</body></html>'


class ReachabilityFootprintTests(unittest.TestCase):
    def test_light_default_caps_probes(self):
        # 15 declared off-sample variants; default (light) must probe only a small bounded set
        block, _ = regions.scan(make_ctx([("https://acme.example/", _many_home(15))]))
        self.assertLessEqual(block["checked"], regions.REGION_PROBES_LIGHT)
        self.assertFalse(block["exhaustive"])
        self.assertIn("--check-regions", block["note"])   # tells the user how to probe all

    def test_exhaustive_probes_more(self):
        block, _ = regions.scan(make_ctx([("https://acme.example/", _many_home(15))]), exhaustive=True)
        self.assertGreater(block["checked"], regions.REGION_PROBES_LIGHT)
        self.assertTrue(block["exhaustive"])


class RegionAuditTests(unittest.TestCase):
    def _block(self):
        return {"count": 3, "variants": [
            {"url": "https://acme.example/", "region": "Global (x-default)", "locale": "x-default",
             "is_default": True, "reachable": "ok"},
            {"url": "https://acme.example/in/", "region": "India", "locale": "en-in", "reachable": "ok"},
            {"url": "https://acme.example/uk/", "region": "United Kingdom", "locale": "en-gb",
             "reachable": "error"},
        ]}

    def test_audit_candidates_skips_primary_and_dead(self):
        cands = regions.audit_candidates(self._block(), "https://acme.example/", limit=3)
        urls = [c["url"] for c in cands]
        self.assertIn("https://acme.example/in/", urls)
        self.assertNotIn("https://acme.example/", urls)      # primary excluded
        self.assertNotIn("https://acme.example/uk/", urls)   # dead excluded

    def _rpt(self, site, value, disc, cite, eng):
        return {"site": site, "score": {"value": value, "grade": "C" if value >= 70 else "F",
                "discoverability": disc, "engagement": eng},
                "citation_readiness": {"score": cite}, "summary": {"total_findings": 3}}

    def test_build_audits_flags_weaker_region(self):
        primary_v = {"url": "https://acme.example/", "region": "Global (x-default)", "locale": "x-default"}
        primary = self._rpt("acme.example", 75, 70, 65, 96)
        india_v = {"url": "https://acme.example/in/", "region": "India", "locale": "en-in"}
        india = self._rpt("acme.example", 54, 38, 42, 88)
        out = regions.build_audits(primary, primary_v, [(india_v, india)])
        self.assertEqual(len(out["regions"]), 2)
        self.assertTrue(out["regions"][0]["is_primary"])
        self.assertIn("India", out["note"])
        self.assertIn("trails", out["note"])


if __name__ == "__main__":
    unittest.main()
