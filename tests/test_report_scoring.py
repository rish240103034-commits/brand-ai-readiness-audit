"""Unit tests for the report builder, schema validation, and scoring/prioritization."""
import unittest

from auditlib import report as R
from auditlib.scoring import score_report, _grade


def mk(sev, dim="discoverability", conf="high", title="t", cat="structured-data"):
    return R.Finding(title=title, severity=sev, evidence="e", suggested_action_summary="fix",
                     suggested_action_priority=sev, dimension=dim, confidence=conf, category=cat)


class ReportTests(unittest.TestCase):
    def test_ids_and_severity_order(self):
        rpt = R.build_report("x.example", [mk("low", title="a"), mk("critical", title="b")])
        self.assertEqual(rpt["findings"][0]["severity"], "critical")
        self.assertEqual(rpt["findings"][0]["id"], "F-001")
        self.assertEqual(rpt["summary"]["total_findings"], 2)

    def test_validate_passes_on_built_report(self):
        rpt = R.build_report("x.example", [mk("high")])
        self.assertEqual(R.validate(rpt), [])

    def test_validate_flags_missing_fields(self):
        broken = {"site": "x", "summary": {}, "findings": [{"title": "t"}]}
        errs = R.validate(broken)
        self.assertTrue(any("audited_at" in e for e in errs))
        self.assertTrue(any("finding[0]" in e for e in errs))

    def test_invalid_severity_normalized(self):
        f = mk("bogus")
        self.assertEqual(f.normalized_severity(), "medium")


class ScoringTests(unittest.TestCase):
    def test_clean_site_scores_high(self):
        rpt = R.build_report("x.example", [])
        score_report(rpt)
        self.assertEqual(rpt["score"]["value"], 100)
        self.assertEqual(rpt["score"]["grade"], "A")

    def test_critical_finding_tanks_discoverability(self):
        rpt = R.build_report("x.example", [mk("critical", dim="discoverability")])
        score_report(rpt)
        self.assertLess(rpt["score"]["discoverability"], 70)
        self.assertLess(rpt["score"]["value"], 90)

    def test_prioritization_orders_by_impact(self):
        rpt = R.build_report("x.example", [mk("low", title="minor"), mk("critical", title="major")])
        score_report(rpt)
        self.assertEqual(rpt["findings"][0]["priority"], 1)
        self.assertEqual(rpt["findings"][0]["severity"], "critical")
        self.assertIn("why", rpt["findings"][0])
        self.assertGreaterEqual(rpt["findings"][0]["impact"], rpt["findings"][1]["impact"])

    def test_grade_bands(self):
        self.assertEqual(_grade(95), "A")
        self.assertEqual(_grade(82), "B")
        self.assertEqual(_grade(71), "C")
        self.assertEqual(_grade(61), "D")
        self.assertEqual(_grade(40), "F")

    def test_low_confidence_tempers_impact(self):
        rpt = R.build_report("x.example", [mk("high", conf="low")])
        score_report(rpt)
        self.assertEqual(rpt["findings"][0]["impact"], 3)  # 4 - 1 for low confidence


if __name__ == "__main__":
    unittest.main()
