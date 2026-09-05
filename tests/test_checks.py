"""Unit tests for all six check modules (pass / fail / edge per skill). No network."""
import unittest

from auditlib.checks import (crawl_render, structured_data, extractability,
                             freshness, corroboration, engagement)
from tests.helpers import make_ctx, GOOD_HOME, BARE_SPA, NO_META_PAGE


def titles(findings):
    return {f.title for f in findings}


def categories(findings):
    return {f.category for f in findings}


class CrawlRenderTests(unittest.TestCase):
    def test_retrieval_bot_blocked_is_critical(self):
        # Blocking a retrieval/citation crawler is critical (removes the brand from live answers).
        robots = "User-agent: PerplexityBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
        ctx = make_ctx([("https://x.example/", GOOD_HOME)], robots=robots, sitemap="<urlset></urlset>")
        f = crawl_render.analyze(ctx)
        self.assertIn("AI answer-engine retrieval crawlers are blocked in robots.txt", titles(f))
        crit = [x for x in f if "retrieval crawlers" in x.title][0]
        self.assertEqual(crit.severity, "critical")

    def test_training_bot_block_is_low_not_critical(self):
        # Blocking only training crawlers is a legitimate policy choice — flagged low, never critical.
        robots = "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
        ctx = make_ctx([("https://x.example/", GOOD_HOME)], robots=robots, sitemap="<urlset></urlset>")
        f = crawl_render.analyze(ctx)
        self.assertIn("AI training crawlers are blocked in robots.txt", titles(f))
        train = [x for x in f if "training crawlers" in x.title][0]
        self.assertEqual(train.severity, "low")
        self.assertFalse(any(x.severity == "critical" for x in f))

    def test_spa_shell_flagged_as_render_gap(self):
        ctx = make_ctx([("https://x.example/", BARE_SPA)], robots="", sitemap="<urlset></urlset>")
        f = crawl_render.analyze(ctx)
        self.assertIn("js-render-gap", categories(f))

    def test_clean_site_has_no_crawl_or_render_findings(self):
        ctx = make_ctx([("https://x.example/", GOOD_HOME)],
                       robots="User-agent: *\nAllow: /\nSitemap: https://x.example/sitemap.xml\n",
                       sitemap="<urlset><url><loc>https://x.example/</loc></url></urlset>")
        f = crawl_render.analyze(ctx)
        self.assertNotIn("js-render-gap", categories(f))
        self.assertFalse(any(x.severity == "critical" for x in f))


class StructuredDataTests(unittest.TestCase):
    def test_absence_flagged(self):
        ctx = make_ctx([("https://x.example/", NO_META_PAGE)])
        self.assertIn("No structured data anywhere in the sampled pages",
                      titles(structured_data.analyze(ctx)))

    def test_invalid_jsonld_flagged(self):
        bad = '<html><head><title>t</title><script type="application/ld+json">{bad,,}</script></head><body>hi</body></html>'
        ctx = make_ctx([("https://x.example/", bad)])
        self.assertIn("Invalid JSON-LD (present but unparseable)", titles(structured_data.analyze(ctx)))

    def test_good_home_has_no_absence_or_identity_finding(self):
        ctx = make_ctx([("https://x.example/", GOOD_HOME)])
        t = titles(structured_data.analyze(ctx))
        self.assertNotIn("No structured data anywhere in the sampled pages", t)
        self.assertNotIn("Homepage lacks Organization/WebSite structured data", t)

    def test_product_url_without_schema_flagged(self):
        prod = '<html><head><title>Widget</title></head><body><h1>Widget</h1><p>$9.99</p></body></html>'
        ctx = make_ctx([("https://x.example/", GOOD_HOME), ("https://x.example/product/widget", prod)])
        self.assertIn("Product-like pages missing Product/Offer schema", titles(structured_data.analyze(ctx)))


class ExtractabilityTests(unittest.TestCase):
    def test_missing_title_and_meta_flagged(self):
        ctx = make_ctx([("https://x.example/", NO_META_PAGE)])
        t = titles(extractability.analyze(ctx))
        self.assertIn("Pages missing a <title>", t)
        self.assertIn("Pages missing a meta description", t)

    def test_missing_alt_flagged(self):
        ctx = make_ctx([("https://x.example/", NO_META_PAGE)])
        self.assertIn("Many images lack alt text", titles(extractability.analyze(ctx)))

    def test_good_home_has_title_and_meta(self):
        ctx = make_ctx([("https://x.example/", GOOD_HOME)])
        t = titles(extractability.analyze(ctx))
        self.assertNotIn("Pages missing a <title>", t)
        self.assertNotIn("Pages missing a meta description", t)


class FreshnessTests(unittest.TestCase):
    def test_stale_copyright_flagged(self):
        stale = '<html lang="en"><head><title>t</title></head><body><p>Welcome to our very old site.</p><footer>© 2010 OldCo</footer></body></html>'
        ctx = make_ctx([("https://x.example/", stale)])
        self.assertIn("Stale copyright year in footer", titles(freshness.analyze(ctx)))

    def test_recent_signal_suppresses_stale(self):
        guarded = '<html lang="en"><head><title>t</title></head><body><p>Last updated 2026.</p><footer>© 2010 OldCo</footer></body></html>'
        ctx = make_ctx([("https://x.example/", guarded)])
        self.assertNotIn("Stale copyright year in footer", titles(freshness.analyze(ctx)))

    def test_undated_article_flagged(self):
        art = '<html lang="en"><head><title>Post</title></head><body><h1>Post</h1><p>5 min read of content here.</p></body></html>'
        ctx = make_ctx([("https://x.example/blog/post", art)])
        self.assertIn("Articles published without a visible date", titles(freshness.analyze(ctx)))


class CorroborationTests(unittest.TestCase):
    def test_org_without_sameas_flagged(self):
        page = '<html lang="en"><head><title>t</title><script type="application/ld+json">{"@type":"Organization","name":"Solo Co"}</script></head><body><p>hi</p></body></html>'
        ctx = make_ctx([("https://x.example/", page)])
        self.assertIn("Organization schema has no sameAs corroboration links", titles(corroboration.analyze(ctx)))

    def test_no_external_presence_flagged(self):
        ctx = make_ctx([("https://x.example/", NO_META_PAGE)])
        self.assertIn("No links to external brand profiles or authority sources", titles(corroboration.analyze(ctx)))

    def test_good_home_has_sameas_and_socials(self):
        ctx = make_ctx([("https://x.example/", GOOD_HOME)])
        t = titles(corroboration.analyze(ctx))
        self.assertNotIn("Organization schema has no sameAs corroboration links", t)
        self.assertNotIn("No links to external brand profiles or authority sources", t)


class EngagementTests(unittest.TestCase):
    def test_missing_viewport_flagged(self):
        ctx = make_ctx([("https://x.example/", NO_META_PAGE)])
        self.assertIn("No responsive viewport meta tag", titles(engagement.analyze(ctx)))

    def test_no_cta_or_nav_flagged(self):
        page = '<html><head><title>t</title></head><body><p>Just text, no actions or menu.</p></body></html>'
        ctx = make_ctx([("https://x.example/", page)])
        t = titles(engagement.analyze(ctx))
        self.assertIn("Homepage has no clear call-to-action", t)
        self.assertIn("No semantic navigation region", t)

    def test_good_home_has_cta_and_nav_and_viewport(self):
        ctx = make_ctx([("https://x.example/", GOOD_HOME)])
        t = titles(engagement.analyze(ctx))
        self.assertNotIn("No responsive viewport meta tag", t)
        self.assertNotIn("Homepage has no clear call-to-action", t)
        self.assertNotIn("No semantic navigation region", t)


if __name__ == "__main__":
    unittest.main()
