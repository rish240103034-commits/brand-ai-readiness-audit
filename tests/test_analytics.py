"""Unit tests for the analyst layer (analytics.py) and the Markdown/CSV exporters."""
import unittest

from auditlib import report as R
from auditlib.scoring import score_report
from auditlib import analytics, exports


def mk(sev, dim="discoverability", cat="structured-data", conf="high", title=None, pages=None):
    return R.Finding(title=title or f"{cat} issue", severity=sev, evidence="evidence text",
                     suggested_action_summary="do the fix", suggested_action_priority=sev,
                     dimension=dim, confidence=conf, category=cat, affected_pages=pages or [])


def scored(findings, **extra):
    rpt = R.build_report("x.example", findings, pages_crawled=extra.pop("pages", 6))
    rpt["profile"] = "balanced"
    rpt["skills_run"] = extra.pop("skills", ["crawl-render-audit", "engagement-audit"])
    score_report(rpt)
    analytics.attach(rpt)
    return rpt


class AttachTests(unittest.TestCase):
    def test_attach_adds_all_blocks(self):
        an = scored([mk("high", cat="crawlability")])["analytics"]
        for key in ("kpis", "pillars", "distribution", "matrix", "quadrant_counts",
                    "quick_wins", "projection", "hotspots", "roadmap", "narrative"):
            self.assertIn(key, an)

    def test_clean_site_is_safe(self):
        an = scored([])["analytics"]
        self.assertEqual(an["kpis"]["total_findings"], 0)
        self.assertEqual(an["quick_wins"], [])
        self.assertEqual(an["projection"]["current"], 100)
        self.assertEqual(an["projection"]["after_all_fixed"], 100)
        self.assertTrue(an["narrative"])  # still produces a sentence

    def test_schema_still_valid_with_analytics(self):
        rpt = scored([mk("critical", cat="crawlability")])
        self.assertEqual(R.validate(rpt), [])


class PillarTests(unittest.TestCase):
    def test_categories_map_to_pillars(self):
        pillars = {p["key"]: p for p in scored([
            mk("high", cat="structured-data"),
            mk("high", dim="engagement", cat="mobile"),
        ])["analytics"]["pillars"]}
        self.assertLess(pillars["structured_data"]["score"], 100)
        self.assertLess(pillars["engagement"]["score"], 100)
        self.assertEqual(pillars["freshness"]["score"], 100)  # untouched pillar stays perfect

    def test_pillar_status_bands(self):
        pillars = {p["key"]: p for p in scored([mk("critical", cat="crawlability")])["analytics"]["pillars"]}
        self.assertEqual(pillars["crawl_render"]["status"], "critical")
        self.assertEqual(pillars["freshness"]["status"], "healthy")


class MatrixTests(unittest.TestCase):
    def test_quick_win_detected(self):
        # critical + crawlability = high impact (5), low effort (2) => quick win
        an = scored([mk("critical", cat="crawlability", title="robots blocks all")])["analytics"]
        self.assertEqual(an["quadrant_counts"]["quick_win"], 1)
        self.assertEqual(an["quick_wins"][0]["title"], "robots blocks all")

    def test_major_project_for_render_gap(self):
        # high + js-render-gap = high impact, high effort (5) => major project
        an = scored([mk("high", cat="js-render-gap")])["analytics"]
        self.assertEqual(an["quadrant_counts"]["major_project"], 1)
        self.assertEqual(an["matrix"][0]["effort"], 5)

    def test_points_at_stake_nonnegative(self):
        an = scored([mk("critical", cat="crawlability"), mk("low", cat="freshness")])["analytics"]
        self.assertTrue(all(m["points_at_stake"] >= 0 for m in an["matrix"]))

    def test_site_wide_per_page_work_costs_more_effort(self):
        # Non-template work (authoring schema) scales with pages -> +1 effort at site scale.
        local = scored([mk("medium", cat="structured-data")])["analytics"]["matrix"][0]["effort"]
        wide = scored([mk("medium", cat="structured-data",
                          pages=[f"https://x/{i}" for i in range(6)])])["analytics"]["matrix"][0]["effort"]
        self.assertEqual(wide, local + 1)

    def test_basic_template_fixes_stay_low_effort_site_wide(self):
        # Basic tag/template fixes (extractability) stay low-effort even across many pages.
        local = scored([mk("medium", cat="extractability")])["analytics"]["matrix"][0]["effort"]
        wide = scored([mk("medium", cat="extractability",
                          pages=[f"https://x/{i}" for i in range(6)])])["analytics"]["matrix"][0]["effort"]
        self.assertEqual(wide, local)          # no bump
        self.assertLessEqual(wide, 2)          # Low


class ProjectionTests(unittest.TestCase):
    def test_projection_is_monotonic(self):
        p = scored([mk("critical", cat="crawlability"), mk("high", dim="engagement", cat="mobile"),
                    mk("medium", cat="extractability")])["analytics"]["projection"]
        self.assertLessEqual(p["current"], p["after_quick_wins"])
        self.assertLessEqual(p["after_quick_wins"], p["after_all_fixed"])
        self.assertEqual(p["after_all_fixed"], 100)

    def test_quick_wins_can_reach_next_grade(self):
        an = scored([mk("critical", cat="crawlability")])["analytics"]
        p = an["projection"]
        self.assertGreater(p["quick_win_gain"], 0)
        self.assertIsNotNone(p["to_next_grade"])


class RoadmapTests(unittest.TestCase):
    def test_buckets(self):
        # medium performance is high-effort, so it is NOT a quick win -> lands in "next".
        rm = scored([
            mk("critical", cat="crawlability", title="crit"),
            mk("medium", dim="engagement", cat="performance", title="med"),
            mk("low", cat="freshness", title="low"),
        ])["analytics"]["roadmap"]
        self.assertIn("crit", [x["title"] for x in rm["now"]])
        self.assertIn("med", [x["title"] for x in rm["next"]])
        self.assertIn("low", [x["title"] for x in rm["later"]])

    def test_medium_quick_win_goes_to_now(self):
        # a low-effort medium finding is a quick win, so it is prioritized into "now".
        rm = scored([mk("medium", cat="extractability", title="qw")])["analytics"]["roadmap"]
        self.assertIn("qw", [x["title"] for x in rm["now"]])


class DistributionTests(unittest.TestCase):
    def test_severity_percentages(self):
        dist = scored([mk("high"), mk("high"), mk("low")])["analytics"]["distribution"]
        by_sev = {d["key"]: d for d in dist["by_severity"]}
        self.assertEqual(by_sev["high"]["count"], 2)
        self.assertEqual(by_sev["high"]["pct"], 67)


class HotspotTests(unittest.TestCase):
    def test_ranked_by_impact(self):
        hs = scored([
            mk("critical", cat="crawlability", pages=["https://x/a"]),
            mk("low", cat="freshness", pages=["https://x/a", "https://x/b"]),
        ])["analytics"]["hotspots"]
        self.assertEqual(hs[0]["url"], "https://x/a")  # carries the critical, highest impact
        self.assertEqual(hs[0]["top_severity"], "critical")


class NarrativeTests(unittest.TestCase):
    def test_mentions_score_and_quick_wins(self):
        narr = " ".join(scored([mk("critical", cat="crawlability")])["analytics"]["narrative"])
        self.assertIn("x.example", narr)
        self.assertIn("quick win", narr.lower())


class ExportTests(unittest.TestCase):
    def test_markdown_has_key_sections(self):
        md = exports.render_markdown(scored([mk("critical", cat="crawlability")]))
        self.assertIn("# AI Readiness Audit", md)
        self.assertIn("AI Visibility Score", md)
        self.assertIn("## Findings", md)
        self.assertIn("Quick wins", md)

    def test_csv_row_per_finding(self):
        rpt = scored([mk("critical", cat="crawlability"), mk("low", cat="freshness")])
        csv_text = exports.findings_csv(rpt)
        lines = [ln for ln in csv_text.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 3)  # header + 2 findings
        self.assertIn("quadrant", lines[0])
        self.assertIn("points_at_stake", lines[0])

    def test_csv_empty_findings_header_only(self):
        csv_text = exports.findings_csv(scored([]))
        lines = [ln for ln in csv_text.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
