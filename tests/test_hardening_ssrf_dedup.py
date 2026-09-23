"""Round-3 hardening: SSRF redirect revalidation + root-cause finding dedup."""
import unittest
import urllib.error

from auditlib import http
from auditlib import report as R
from auditlib.report import Finding, build_report


class SafeRedirectTests(unittest.TestCase):
    def _redirect(self, newurl):
        h = http._SafeRedirectHandler()
        # minimal stand-ins for the urllib redirect_request signature
        req = urllib_request_stub()
        return h.redirect_request(req, FpStub(), 302, "Found", {}, newurl)

    def test_redirect_to_private_ip_blocked(self):
        with self.assertRaises(urllib.error.HTTPError):
            self._redirect("http://169.254.169.254/latest/meta-data/")

    def test_redirect_to_localhost_blocked(self):
        with self.assertRaises(urllib.error.HTTPError):
            self._redirect("http://127.0.0.1/admin")

    def test_redirect_to_nonhttp_scheme_blocked(self):
        with self.assertRaises(urllib.error.HTTPError):
            self._redirect("file:///etc/passwd")

    def test_redirect_to_public_host_allowed(self):
        # a public host should be permitted (returns a Request, not an error)
        out = self._redirect("https://example.org/moved")
        self.assertIsNotNone(out)


class DedupTests(unittest.TestCase):
    def _f(self, title, sev="high", dim="discoverability", cat="structured-data", pages=None):
        return Finding(title=title, severity=sev, evidence="e",
                       suggested_action_summary="s", suggested_action_priority=sev,
                       category=cat, dimension=dim, affected_pages=pages or [])

    def test_same_root_cause_collapsed_and_pages_merged(self):
        f1 = self._f("No structured data anywhere", pages=["/a"])
        f2 = self._f("no structured data anywhere", pages=["/b", "/a"])  # case/space variant
        rpt = build_report("x.example", [f1, f2], pages_crawled=2)
        titles = [f["title"] for f in rpt["findings"]]
        self.assertEqual(len(titles), 1)                       # collapsed to one
        self.assertEqual(rpt["summary"]["total_findings"], 1)
        self.assertCountEqual(rpt["findings"][0]["affected_pages"], ["/a", "/b"])

    def test_stronger_severity_wins_as_primary(self):
        f_low = self._f("Same issue", sev="low")
        f_crit = self._f("Same issue", sev="critical")
        rpt = build_report("x.example", [f_low, f_crit], pages_crawled=1)
        self.assertEqual(len(rpt["findings"]), 1)
        self.assertEqual(rpt["findings"][0]["severity"], "critical")

    def test_distinct_findings_preserved(self):
        f1 = self._f("No structured data", cat="structured-data")
        f2 = self._f("Broken internal links", cat="crawlability")
        rpt = build_report("x.example", [f1, f2], pages_crawled=1)
        self.assertEqual(len(rpt["findings"]), 2)              # different root causes kept


# --- tiny stubs so we can call redirect_request without a live socket -----------------
class FpStub:
    def read(self, *a):
        return b""
    def close(self):
        pass


def urllib_request_stub():
    import urllib.request
    return urllib.request.Request("https://start.example/")


if __name__ == "__main__":
    unittest.main()
