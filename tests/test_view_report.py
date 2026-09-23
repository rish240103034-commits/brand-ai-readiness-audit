"""Offline test for the Round-4 read-only report viewer (round4/view_report.py).

Feeds the committed example report through the viewer and asserts it renders the summary
and a single-finding drill-down without error. No network, no engine invocation.
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROUND4 = os.path.join(_ROOT, "round4")
if _ROUND4 not in sys.path:
    sys.path.insert(0, _ROUND4)

import view_report  # noqa: E402

_SAMPLE = os.path.join(_ROOT, "examples", "sample-report.json")


class ViewReportTest(unittest.TestCase):
    def test_summary_renders(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = view_report.main([_SAMPLE])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("AI Visibility Score", out)
        self.assertIn("Prioritized findings", out)

    def test_top_n_limits(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            view_report.main([_SAMPLE, "--top", "3"])
        self.assertIn("showing 3 of", buf.getvalue())

    def test_finding_drilldown(self):
        rpt = view_report.load(_SAMPLE)
        fid = rpt["findings"][0]["id"]
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = view_report.main([_SAMPLE, "--finding", fid])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("evidence", out)
        self.assertIn("suggested fix", out)

    def test_missing_report_is_graceful(self):
        code = view_report.main([os.path.join(_ROOT, "no_such_report.json")])
        self.assertEqual(code, 2)  # bad input, not a crash


if __name__ == "__main__":
    unittest.main()
