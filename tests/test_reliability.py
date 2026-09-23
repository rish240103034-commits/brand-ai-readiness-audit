"""Tests for the thin-crawl confidence guard."""
import unittest

from auditlib import reliability


class AssessTests(unittest.TestCase):
    def test_thin_crawl_is_provisional(self):
        b = reliability.assess(pages_readable=1, http_failures=8, requests_made=2)
        self.assertTrue(b["provisional"])
        self.assertEqual(b["confidence"], "low")
        self.assertIn("blocked", b["reason"])
        self.assertIn("8 fetch", b["reason"])

    def test_thin_without_failures_still_provisional_but_worded_differently(self):
        b = reliability.assess(pages_readable=2, http_failures=0)
        self.assertTrue(b["provisional"])
        self.assertIn("limited evidence", b["reason"])

    def test_healthy_crawl_is_ok(self):
        b = reliability.assess(pages_readable=12, http_failures=1)
        self.assertFalse(b["provisional"])
        self.assertEqual(b["confidence"], "ok")
        self.assertEqual(b["reason"], "")


class ApplyTests(unittest.TestCase):
    def test_apply_marks_score_and_notes_when_provisional(self):
        rpt = {"score": {"value": 65, "grade": "D", "headline": "AI Visibility Score 65/100 (D)"},
               "notes": ["Crawled 1 page(s)."]}
        reliability.apply(rpt, reliability.assess(1, http_failures=5))
        self.assertTrue(rpt["score"]["provisional"])
        self.assertEqual(rpt["score"]["confidence"], "low")
        self.assertTrue(rpt["score"]["headline"].startswith("Provisional — "))
        self.assertTrue(rpt["notes"][0].startswith("LOW CONFIDENCE:"))
        self.assertEqual(rpt["reliability"]["pages_readable"], 1)

    def test_apply_leaves_healthy_report_untouched(self):
        rpt = {"score": {"value": 80, "grade": "B", "headline": "AI Visibility Score 80/100 (B)"},
               "notes": []}
        reliability.apply(rpt, reliability.assess(10))
        self.assertNotIn("provisional", rpt["score"])
        self.assertEqual(rpt["score"]["headline"], "AI Visibility Score 80/100 (B)")
        self.assertEqual(rpt["notes"], [])
        self.assertFalse(rpt["reliability"]["provisional"])

    def test_headline_not_double_prefixed(self):
        rpt = {"score": {"headline": "Provisional — AI Visibility Score 65/100 (D)"}, "notes": []}
        reliability.apply(rpt, reliability.assess(1))
        self.assertEqual(rpt["score"]["headline"].count("Provisional"), 1)


if __name__ == "__main__":
    unittest.main()
