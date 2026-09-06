"""Tests for the winning-tier modules: visibility funnel, competitor benchmark, fix snippets/plan."""
import unittest

import eval as ev
from auditlib import report as R, funnel, benchmark, snippets, analytics, render, exports
from auditlib.scoring import score_report
from tests.helpers import make_ctx, GOOD_HOME


def mk(sev, cat, dim="discoverability"):
    return R.Finding(title=f"{cat} issue", severity=sev, evidence="e", suggested_action_summary="fix",
                     suggested_action_priority=sev, dimension=dim, category=cat)


def scored(findings):
    rpt = R.build_report("x.example", findings, pages_crawled=5)
    rpt["skills_run"] = ["crawl-render-audit", "structured-data-audit"]
    score_report(rpt)
    return rpt


class FunnelTests(unittest.TestCase):
    def test_gates_and_weakest(self):
        rpt = scored([mk("critical", "js-render-gap"), mk("low", "freshness")])
        fn = funnel.build(rpt)
        keys = [g["key"] for g in fn["gates"]]
        self.assertEqual(keys, ["reach", "read", "quote", "trust"])
        self.assertEqual(fn["weakest"], "read")   # js-render-gap tanks the Read gate

    def test_clean_all_gates_high(self):
        fn = funnel.build(scored([]))
        self.assertTrue(all(g["score"] == 100 for g in fn["gates"]))


class BenchmarkTests(unittest.TestCase):
    def _rpt(self, site, score, sd_pillar):
        return {"site": site, "score": {"value": score, "grade": "C"},
                "analytics": {"pillars": [{"key": "structured_data", "score": sd_pillar},
                                          {"key": "engagement", "score": 90}]},
                "answer_readiness": {"score": 2, "applicable": 4},
                "summary": {"total_findings": 5}}

    def test_gap_detected(self):
        primary = self._rpt("you.com", 60, 40)
        comps = [self._rpt("rival.com", 82, 90)]
        b = benchmark.build(primary, comps)
        self.assertEqual(b["you"]["site"], "you.com")
        self.assertTrue(any(g["pillar"] == "Structured Data" for g in b["gaps"]))

    def test_no_gap_when_ahead(self):
        b = benchmark.build(self._rpt("you.com", 90, 95), [self._rpt("rival.com", 60, 50)])
        self.assertEqual(b["gaps"], [])


class SnippetsTests(unittest.TestCase):
    def test_attach_adds_snippet_and_plan(self):
        # a report with a "No structured data" finding should get a JSON-LD snippet + a fix plan
        f = R.Finding(title="No structured data anywhere in the sampled pages", severity="high",
                      evidence="e", suggested_action_summary="add schema", suggested_action_priority="high",
                      category="structured-data")
        rpt = R.build_report("acme.example", [f], pages_crawled=1)
        rpt["skills_run"] = ["structured-data-audit"]
        score_report(rpt)
        analytics.attach(rpt)
        ctx = make_ctx([("https://acme.example/", GOOD_HOME)])
        snippets.attach(rpt, ctx)
        self.assertIn("application/ld+json", rpt["findings"][0].get("fix_snippet", ""))
        self.assertTrue(rpt["fix_plan"])
        self.assertEqual(rpt["fix_plan"][0]["finding_id"], rpt["findings"][0]["id"])
        self.assertTrue(rpt["fix_plan"][0]["has_snippet"])

    def test_snippet_uses_brand_name(self):
        f = R.Finding(title="Homepage lacks Organization/WebSite structured data", severity="medium",
                      evidence="e", suggested_action_summary="add org", suggested_action_priority="medium",
                      category="entity-identity")
        rpt = R.build_report("acme.example", [f], pages_crawled=1); rpt["skills_run"] = []
        score_report(rpt); analytics.attach(rpt)
        snippets.attach(rpt, make_ctx([("https://acme.example/", GOOD_HOME)]))
        self.assertIn("Acme Robotics", rpt["findings"][0]["fix_snippet"])  # from GOOD_HOME schema


class RenderSmokeTests(unittest.TestCase):
    """Render every output format on a full report — catches crashes like a missing import."""
    @classmethod
    def setUpClass(cls):
        cls.rpt = ev._serve_and_audit(ev.FIXTURES["no_schema_commerce"])

    def test_html_renders_with_key_sections(self):
        h = render.render_html(self.rpt)
        self.assertGreater(len(h), 5000)
        for marker in ("AI Visibility Score", "Visibility funnel", "Findings", "audit-data"):
            self.assertIn(marker, h)

    def test_markdown_and_csv_render(self):
        self.assertIn("# AI Readiness Audit", exports.render_markdown(self.rpt))
        self.assertIn("id,priority,severity", exports.findings_csv(self.rpt))


if __name__ == "__main__":
    unittest.main()
