"""Tests for the v2.4 additions: hreflang/i18n, AI answer-readiness, and llms.txt."""
import unittest

from auditlib.checks import crawl_render
from auditlib import answer_readiness, llmstxt
from tests.helpers import make_ctx, GOOD_HOME


def titles(findings):
    return {f.title for f in findings}


HREF_TWO_LANG = ('<html lang="en"><head><title>t</title>'
                 '<link rel="alternate" hreflang="en" href="https://x.example/en">'
                 '<link rel="alternate" hreflang="fr" href="https://x.example/fr">'
                 '</head><body><p>hi</p></body></html>')
HREF_BAD_CODE = ('<html lang="en"><head><title>t</title>'
                 '<link rel="alternate" hreflang="english" href="https://x.example/en">'
                 '<link rel="alternate" hreflang="x-default" href="https://x.example/">'
                 '</head><body><p>hi</p></body></html>')


class HreflangTests(unittest.TestCase):
    def test_missing_x_default_flagged(self):
        ctx = make_ctx([("https://x.example/", HREF_TWO_LANG)])
        self.assertIn("hreflang set without an x-default", titles(crawl_render.analyze(ctx)))

    def test_invalid_code_flagged(self):
        ctx = make_ctx([("https://x.example/", HREF_BAD_CODE)])
        self.assertIn("Invalid hreflang language codes", titles(crawl_render.analyze(ctx)))

    def test_single_language_site_not_flagged(self):
        ctx = make_ctx([("https://x.example/", GOOD_HOME)])
        t = titles(crawl_render.analyze(ctx))
        self.assertNotIn("hreflang set without an x-default", t)
        self.assertNotIn("Invalid hreflang language codes", t)


class AnswerReadinessTests(unittest.TestCase):
    def test_identity_machine_readable_with_schema(self):
        ctx = make_ctx([("https://acme.example/", GOOD_HOME)])
        ar = answer_readiness.build(ctx)
        idn = [i for i in ar["items"] if i["key"] == "identity"][0]
        self.assertEqual(idn["state"], "machine_readable")

    def test_pricing_hours_na_without_commerce(self):
        ctx = make_ctx([("https://acme.example/", GOOD_HOME)])
        st = {i["key"]: i["state"] for i in answer_readiness.build(ctx)["items"]}
        self.assertEqual(st["pricing"], "n/a")
        self.assertEqual(st["hours"], "n/a")

    def test_score_within_applicable(self):
        ar = answer_readiness.build(make_ctx([("https://acme.example/", GOOD_HOME)]))
        self.assertLessEqual(ar["score"], ar["applicable"])
        self.assertGreaterEqual(ar["applicable"], 1)


class LlmsTxtTests(unittest.TestCase):
    def test_absent_generates_suggestion(self):
        ctx = make_ctx([("https://acme.example/", GOOD_HOME)])  # FakeFetcher 404s /llms.txt
        lt = llmstxt.build(ctx)
        self.assertFalse(lt["present"])
        self.assertIn("# Acme Robotics", lt["suggested"])
        self.assertIn("## Key pages", lt["suggested"])

    def test_key_pages_included(self):
        pages = [("https://acme.example/", GOOD_HOME),
                 ("https://acme.example/about", "<html><head><title>About</title></head><body></body></html>"),
                 ("https://acme.example/products", "<html><head><title>Products</title></head><body></body></html>")]
        lt = llmstxt.build(make_ctx(pages))
        self.assertIn("/about", lt["suggested"])
        self.assertIn("/products", lt["suggested"])


if __name__ == "__main__":
    unittest.main()
