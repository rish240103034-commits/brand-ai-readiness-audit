"""Tests for the coverage matrix, proactive opportunities, and the richer evidence model."""
import unittest

from auditlib import coverage, proactive, pages as pages_mod, report as R
from auditlib import render
from auditlib.scoring import score_report
from tests.helpers import make_ctx, GOOD_HOME


def base_report(findings=None, skills=None, pages=5, opps=None):
    return {
        "findings": findings or [],
        "skills_run": skills if skills is not None else
        ["crawl-render-audit", "structured-data-audit", "content-extractability-audit",
         "freshness-corroboration", "engagement-audit"],
        "pages_crawled": pages,
        "opportunities": opps or [],
    }


def find(cat, sev="medium", conf="high"):
    return {"category": cat, "severity": sev, "confidence": conf, "kind": "defect"}


def by_key(cov):
    return {a["key"]: a for a in cov["areas"]}


class CoverageTests(unittest.TestCase):
    def test_skill_not_run_is_not_assessed(self):
        cov = coverage.build(base_report(skills=["crawl-render-audit"]), {"date_signal_pages": 2})
        areas = by_key(cov)
        self.assertEqual(areas["structured_data"]["status"], "not_assessed")
        self.assertEqual(areas["crawlability"]["status"], "healthy")

    def test_freshness_not_assessed_without_dates(self):
        cov = coverage.build(base_report(), {"date_signal_pages": 0})
        self.assertEqual(by_key(cov)["freshness"]["status"], "not_assessed")

    def test_freshness_healthy_with_dates(self):
        cov = coverage.build(base_report(), {"date_signal_pages": 4})
        self.assertEqual(by_key(cov)["freshness"]["status"], "healthy")

    def test_corroboration_partial_when_clean(self):
        # Corroboration inspects on-page signals only -> never 'verified healthy'.
        cov = coverage.build(base_report(), {"date_signal_pages": 2})
        self.assertEqual(by_key(cov)["corroboration"]["status"], "partial")

    def test_corroboration_issues_with_finding(self):
        cov = coverage.build(base_report(findings=[find("corroboration")]), {"date_signal_pages": 2})
        self.assertEqual(by_key(cov)["corroboration"]["status"], "issues")

    def test_area_issues_when_findings(self):
        cov = coverage.build(base_report(findings=[find("structured-data")]), {"date_signal_pages": 2})
        self.assertEqual(by_key(cov)["structured_data"]["status"], "issues")

    def test_summary_counts(self):
        cov = coverage.build(base_report(skills=["crawl-render-audit"]), {"date_signal_pages": 0})
        s = cov["summary"]
        self.assertEqual(s["areas_total"], 8)
        self.assertGreaterEqual(s["areas_not_assessed"], 1)

    def test_no_pages_all_not_assessed(self):
        cov = coverage.build(base_report(pages=0), {"date_signal_pages": 0})
        self.assertTrue(all(a["status"] == "not_assessed" for a in cov["areas"] if a["key"] != "proactive"))

    def test_proactive_area_reflects_opportunities(self):
        cov = coverage.build(base_report(opps=[{"id": "OP-001"}]), {"date_signal_pages": 2})
        self.assertEqual(by_key(cov)["proactive"]["status"], "opportunities")


class ProactiveTests(unittest.TestCase):
    def test_author_opportunity_when_articles_without_author(self):
        art = ('<html lang="en"><head><title>Post</title></head><body>'
               '<h1>Post</h1><p>5 min read of content.</p></body></html>')
        ctx = make_ctx([("https://x.example/", GOOD_HOME), ("https://x.example/blog/post", art)])
        titles = {o["title"] for o in proactive.build(ctx)}
        self.assertIn("Add author (Person) markup to articles", titles)

    def test_product_rating_opportunity(self):
        prod = ('<html lang="en"><head><title>Widget</title>'
                '<script type="application/ld+json">{"@type":"Product","name":"Widget","offers":{"@type":"Offer","price":"9"}}</script>'
                '</head><body><h1>Widget</h1></body></html>')
        ctx = make_ctx([("https://x.example/", prod)])
        titles = {o["title"] for o in proactive.build(ctx)}
        self.assertIn("Add ratings/reviews markup to products", titles)

    def test_no_opportunity_without_justification(self):
        # A plain page with no articles/products/deep pages -> no author/product/breadcrumb opps.
        plain = '<html lang="en"><head><title>Home page of Acme</title></head><body><h1>Acme</h1><p>Hello there friends.</p></body></html>'
        ctx = make_ctx([("https://x.example/", plain)])
        titles = {o["title"] for o in proactive.build(ctx)}
        self.assertNotIn("Add author (Person) markup to articles", titles)
        self.assertNotIn("Add ratings/reviews markup to products", titles)

    def test_ids_assigned(self):
        art = '<html lang="en"><head><title>P</title></head><body><h1>P</h1><p>3 min read here.</p></body></html>'
        ctx = make_ctx([("https://x.example/", GOOD_HOME), ("https://x.example/blog/p", art)])
        opps = proactive.build(ctx)
        if opps:
            self.assertTrue(opps[0]["id"].startswith("OP-"))
            self.assertEqual(opps[0]["kind"], "opportunity")


class DynamicFilterTests(unittest.TestCase):
    def test_no_empty_severity_options(self):
        # Only severities that occur should appear as options (no empty 'Critical'/'High').
        findings = [{"dimension": "discoverability", "severity": "low", "confidence": "high"},
                    {"dimension": "discoverability", "severity": "medium", "confidence": "high"}]
        html = render._filter_controls(findings)
        self.assertIn('id="f-severity"', html)
        self.assertIn('value="low"', html)
        self.assertIn('value="medium"', html)
        self.assertNotIn('value="critical"', html)
        self.assertNotIn('value="high"', html)

    def test_no_single_dimension_filter(self):
        # If every finding is one dimension, don't show a dimension filter at all.
        findings = [{"dimension": "discoverability", "severity": "low", "confidence": "high"},
                    {"dimension": "discoverability", "severity": "high", "confidence": "high"}]
        self.assertNotIn('id="f-dimension"', render._filter_controls(findings))

    def test_search_and_sort_always_present_with_findings(self):
        findings = [{"dimension": "discoverability", "severity": "low", "confidence": "high"},
                    {"dimension": "engagement", "severity": "high", "confidence": "medium"}]
        html = render._filter_controls(findings)
        self.assertIn('id="f-search"', html)
        self.assertIn('id="f-sort"', html)
        self.assertIn('id="f-dimension"', html)  # both dimensions present -> shown

    def test_controls_hidden_for_single_finding(self):
        self.assertEqual(render._filter_controls([{"dimension": "discoverability", "severity": "low"}]), "")


class SectionAnalysisTests(unittest.TestCase):
    def _pages(self):
        return [
            {"url": "https://x/", "score": 60, "finding_ids": ["F-001"]},
            {"url": "https://x/products/a", "score": 40, "finding_ids": ["F-002", "F-003"]},
            {"url": "https://x/products/b", "score": 42, "finding_ids": ["F-002"]},
            {"url": "https://x/blog/p", "score": 85, "finding_ids": []},
        ]

    def _findings(self):
        return [{"id": "F-001", "severity": "medium", "dimension": "discoverability"},
                {"id": "F-002", "severity": "high", "dimension": "discoverability"},
                {"id": "F-003", "severity": "low", "dimension": "engagement"}]

    def test_groups_by_path_and_sorts_weakest_first(self):
        secs = pages_mod.build_sections(self._pages(), self._findings())
        self.assertEqual(secs[0]["key"], "/products")  # lowest average score first
        self.assertEqual(secs[0]["pages"], 2)
        keys = {s["key"] for s in secs}
        self.assertEqual(keys, {"/", "/products", "/blog"})

    def test_distinct_findings_per_section(self):
        secs = {s["key"]: s for s in pages_mod.build_sections(self._pages(), self._findings())}
        # F-002 affects both product pages but counts once for the section.
        self.assertEqual(secs["/products"]["findings"], 2)
        self.assertEqual(secs["/products"]["top_severity"], "high")

    def test_single_section_returns_empty(self):
        one = [{"url": "https://x/", "score": 50, "finding_ids": []}]
        self.assertEqual(pages_mod.build_sections(one, []), [])


class ScoringModelTests(unittest.TestCase):
    def test_scoring_model_attached(self):
        rpt = R.build_report("x.example", [])
        score_report(rpt)
        m = rpt.get("scoring_model")
        self.assertIsNotNone(m)
        self.assertIn("severity_penalty", m)
        self.assertIn("confidence_factor", m)
        self.assertIn("weights", m)
        self.assertEqual(m["severity_penalty"]["critical"], 35)


class EvidenceModelTests(unittest.TestCase):
    def test_rich_fields_emitted_when_present(self):
        f = R.Finding(title="t", severity="high", evidence="e", suggested_action_summary="s",
                      suggested_action_priority="high", why="specific reason",
                      how_to_fix="do this", scope="3 of 5 pages", measurements={"n": 3},
                      expected_impact="better")
        d = f.to_dict()
        for k in ("why", "how_to_fix", "scope", "measurements", "expected_impact"):
            self.assertIn(k, d)

    def test_rich_fields_omitted_when_empty(self):
        f = R.Finding(title="t", severity="high", evidence="e", suggested_action_summary="s",
                      suggested_action_priority="high")
        d = f.to_dict()
        for k in ("why", "how_to_fix", "scope", "measurements", "expected_impact"):
            self.assertNotIn(k, d)

    def test_scope_str(self):
        self.assertEqual(R.scope_str(3, 12), "3 of 12 page(s) (25%)")
        self.assertEqual(R.scope_str(1, 0), "1 page(s)")


if __name__ == "__main__":
    unittest.main()
