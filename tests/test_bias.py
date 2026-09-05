"""Regression tests for site-type fairness — each asserts a previously-biased check no
longer penalizes a site for its language, architecture host layout, or brand-name length."""
import unittest

from auditlib import http, htmlparse
from auditlib.checks import engagement, crawl_render, corroboration
from tests.helpers import make_ctx


def titles(findings):
    return {f.title for f in findings}


def cats(findings):
    return {f.category for f in findings}


class LanguageNeutralCTATests(unittest.TestCase):
    """A non-English homepage with a real CTA must not be flagged for lacking English words."""
    JP_WITH_CART = ('<html lang="ja"><head><title>ストア</title>'
                    '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
                    '<body><nav><a href="/">ホーム</a><a href="/products">製品</a></nav>'
                    '<h1>ようこそ</h1><p>高品質な製品をお届けします。</p>'
                    '<a href="/cart">カートに追加</a></body></html>')
    HI_WITH_CTA_CLASS = ('<html lang="hi"><head><title>दुकान</title></head><body>'
                         '<h1>नमस्ते</h1><p>हमारे उत्पाद देखें।</p>'
                         '<a class="btn" href="/x">अभी खरीदें</a></body></html>')
    NO_ACTION = ('<html lang="ja"><head><title>t</title></head><body>'
                 '<p>ただのテキストです。</p></body></html>')

    def test_conversion_path_link_counts_as_cta(self):
        ctx = make_ctx([("https://x.example/", self.JP_WITH_CART)])
        self.assertNotIn("Homepage has no clear call-to-action", titles(engagement.analyze(ctx)))

    def test_cta_class_counts_as_cta(self):
        ctx = make_ctx([("https://x.example/", self.HI_WITH_CTA_CLASS)])
        self.assertNotIn("Homepage has no clear call-to-action", titles(engagement.analyze(ctx)))

    def test_genuinely_actionless_page_still_flagged(self):
        # De-biasing must not silently disable the check for pages that truly lack a CTA.
        ctx = make_ctx([("https://x.example/", self.NO_ACTION)])
        self.assertIn("Homepage has no clear call-to-action", titles(engagement.analyze(ctx)))


class CJKWordCountTests(unittest.TestCase):
    def test_english_count_unchanged(self):
        self.assertEqual(htmlparse.count_words("hello world foo"), 3)
        self.assertEqual(htmlparse.count_words(""), 0)

    def test_cjk_characters_counted(self):
        # 40 ideographs carry ~40 words of meaning, not 1 whitespace token.
        self.assertGreaterEqual(htmlparse.count_words("产品介绍" * 10), 40)

    def test_mixed_script(self):
        # "Model" + "X" = 2 Latin words; 型号说明 = 4 CJK characters => 6 units.
        self.assertEqual(htmlparse.count_words("Model X 型号 说明"), 6)

    def test_cjk_page_not_flagged_as_render_gap(self):
        body = ("<html lang=\"zh\"><head><title>产品</title></head><body><h1>产品介绍</h1><p>"
                + "这是一段关于我们公司产品的详细介绍。" * 20 + "</p></body></html>")
        ctx = make_ctx([("https://x.example/", body)])
        self.assertNotIn("js-render-gap", cats(crawl_render.analyze(ctx)))


class HostScopeTests(unittest.TestCase):
    def test_same_host_treats_www_and_apex_equal(self):
        self.assertTrue(http.same_host("https://www.x.com/a", "https://x.com/b"))
        self.assertTrue(http.same_host("https://x.com/a", "https://x.com/b"))

    def test_same_host_separates_subdomains(self):
        self.assertFalse(http.same_host("https://x.com", "https://support.x.com"))
        self.assertFalse(http.same_host("https://shop.x.com", "https://blog.x.com"))

    def test_internal_links_host_scope_excludes_subdomains(self):
        body = ('<a href="/page1">a</a>'
                '<a href="https://x.example/page2">b</a>'
                '<a href="https://www.x.example/page3">c</a>'
                '<a href="https://support.x.example/help">d</a>')
        resp = http.Response(url="https://www.x.example/", final_url="https://www.x.example/",
                             status=200, headers={}, body=body, raw_len=len(body),
                             content_type="text/html", elapsed_ms=1, ok=True, error=None)
        links = http._internal_links(resp, "https://www.x.example/", in_scope=http.same_host)
        self.assertTrue(any("/page1" in u for u in links))
        self.assertTrue(any("/page3" in u for u in links))
        self.assertFalse(any("support.x.example" in u for u in links))

    def test_domain_scope_still_available(self):
        self.assertIs(http.scope_predicate("domain"), http.same_registrable_domain)
        self.assertIs(http.scope_predicate("host"), http.same_host)


class BrandNameLengthBiasRemovedTests(unittest.TestCase):
    def test_short_generic_name_not_penalized(self):
        # A short brand name with no schema must not produce a name-ambiguity finding.
        page = ('<html lang="en"><head><title>Nova</title>'
                '<meta property="og:site_name" content="Nova"></head>'
                '<body><h1>Nova</h1><p>We make things.</p></body></html>')
        ctx = make_ctx([("https://nova.example/", page)])
        t = titles(corroboration.analyze(ctx))
        self.assertNotIn("Brand name is ambiguous with no disambiguating signals", t)


if __name__ == "__main__":
    unittest.main()
