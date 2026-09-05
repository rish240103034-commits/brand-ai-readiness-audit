"""Unit tests for URL handling and SSRF-safe target validation (no live network)."""
import unittest

from auditlib import http
from auditlib.config import make_config


class UrlHelperTests(unittest.TestCase):
    def test_ensure_url_adds_scheme(self):
        self.assertEqual(http.ensure_url("example.com"), "https://example.com/")

    def test_ensure_url_extracts_markdown_link(self):
        self.assertEqual(
            http.ensure_url("[www.example.com](https://www.example.com)"),
            "https://www.example.com/")

    def test_ensure_url_strips_wrappers(self):
        self.assertEqual(http.ensure_url("<https://example.com>"), "https://example.com/")
        self.assertEqual(http.ensure_url("`example.com`"), "https://example.com/")

    def test_classify_host_literals(self):
        self.assertEqual(http.classify_host("127.0.0.1"), "loopback")
        self.assertEqual(http.classify_host("10.0.0.1"), "private")
        self.assertEqual(http.classify_host("8.8.8.8"), "public")

    def test_normalize_rejects_non_http(self):
        self.assertIsNone(http.normalize("mailto:x@y.com"))
        self.assertIsNone(http.normalize("javascript:void(0)"))

    def test_same_registrable_domain(self):
        self.assertTrue(http.same_registrable_domain("https://a.example.com/x", "https://example.com/y"))
        self.assertFalse(http.same_registrable_domain("https://example.com", "https://other.com"))

    def test_two_label_suffix(self):
        self.assertTrue(http.same_registrable_domain("https://shop.acme.co.uk", "https://acme.co.uk"))


class SSRFTests(unittest.TestCase):
    def setUp(self):
        self.cfg = make_config("balanced")

    def test_private_ip_literals_blocked(self):
        for host in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.1.1", "localhost"):
            self.assertTrue(http._is_private_host(host), host)

    def test_public_ip_allowed(self):
        self.assertFalse(http._is_private_host("8.8.8.8"))

    def test_validate_rejects_non_http_scheme(self):
        ok, _, reason = http.validate_target("ftp://example.com", self.cfg)
        self.assertFalse(ok)
        self.assertIn("scheme", reason)

    def test_validate_rejects_localhost(self):
        ok, _, reason = http.validate_target("http://localhost:8000", self.cfg)
        self.assertFalse(ok)
        self.assertIn("blocked for SSRF safety", reason)

    def test_validate_allows_private_when_opted_in(self):
        cfg = make_config("balanced").derive(allow_private_hosts=True)
        ok, url, _ = http.validate_target("http://127.0.0.1:8000", cfg)
        self.assertTrue(ok)
        self.assertTrue(url.startswith("http://127.0.0.1"))

    def test_validate_rejects_empty(self):
        ok, _, reason = http.validate_target("", self.cfg)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
