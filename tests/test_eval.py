"""Runs the generalization/false-positive eval harness as part of the suite (fully offline).

Proves the marketplace generalizes: recall 1.0 on the labeled "bad" fixtures and zero false
positives on the clean + non-English fixtures.
"""
import unittest

import eval as ev  # scripts/ is on sys.path via tests/__init__


class EvalHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.summary = ev.evaluate()

    def test_all_fixtures_pass(self):
        failed = [r["fixture"] for r in self.rows if not r["pass"]]
        self.assertEqual(failed, [], f"fixtures failed: {failed}")

    def test_full_recall_on_bad_fixtures(self):
        self.assertEqual(self.summary["recall"], 1.0)

    def test_no_false_positives(self):
        self.assertEqual(self.summary["false_positive_flags"], 0)

    def test_clean_site_has_zero_findings(self):
        clean = {r["fixture"]: r for r in self.rows}["clean"]
        self.assertEqual(clean["findings"], 0)


if __name__ == "__main__":
    unittest.main()
