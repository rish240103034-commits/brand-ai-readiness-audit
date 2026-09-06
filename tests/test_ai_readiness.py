"""Tests for the AI-readiness fact layer: claim extraction, citation readiness,
and AI answer simulation (v2.7)."""
import unittest

from auditlib import claims, citation, answersim, consistency, search_provider
from auditlib.config import make_config
from auditlib.http import _page_type_rank
from tests.helpers import make_ctx, GOOD_HOME

SUPERLATIVE_HOME = ("<!doctype html><html lang=\"en\"><head><title>Zappo</title></head><body>"
                    "<h1>Zappo</h1><p>Zappo is the world's #1 provider of gizmos and the leading "
                    "platform for widgets.</p></body></html>")

# A commerce-ish page whose facts live only in prose (no schema) — should be text_only.
TEXT_ONLY = ("<!doctype html><html lang=\"en\"><head><title>Nimbus Tools</title></head><body>"
             "<h1>Nimbus Tools</h1><p>Nimbus Tools was founded in 2015. We sell garden equipment.</p>"
             "<a href=\"/shop\">Shop</a><p>Prices from $19.99.</p></body></html>")


def by_type(inv):
    out = {}
    for c in inv["claims"]:
        out.setdefault(c["type"], []).append(c)
    return out


class ClaimExtractionTests(unittest.TestCase):
    def test_schema_backed_fact_is_quotable(self):
        ctx = make_ctx([("https://acme.example/", GOOD_HOME)])
        inv = claims.build(ctx)
        bt = by_type(inv)
        self.assertIn("brand_name", bt)
        self.assertEqual(bt["brand_name"][0]["status"], "quotable")   # in schema name AND visible text
        self.assertEqual(bt["brand_name"][0]["value"], "Acme Robotics")

    def test_prose_fact_is_text_only(self):
        ctx = make_ctx([("https://nimbus.example/", TEXT_ONLY)])
        bt = by_type(claims.build(ctx))
        self.assertIn("founding_year", bt)
        self.assertEqual(bt["founding_year"][0]["value"], "2015")
        self.assertEqual(bt["founding_year"][0]["status"], "text_only")  # only in prose, no schema

    def test_sameas_links_become_offsite_identity_claims(self):
        ctx = make_ctx([("https://acme.example/", GOOD_HOME)])
        bt = by_type(claims.build(ctx))
        self.assertIn("identity_link", bt)
        self.assertTrue(all(c["off_site"] for c in bt["identity_link"]))

    def test_consistency_conflict_marks_claim_contradicted(self):
        ctx = make_ctx([("https://nimbus.example/", TEXT_ONLY)])
        block = {"conflicts": [{"type": "founding_year", "label": "Founding year"}]}
        bt = by_type(claims.build(ctx, consistency_block=block))
        self.assertEqual(bt["founding_year"][0]["status"], "contradicted")

    def test_summary_percentages(self):
        inv = claims.build(make_ctx([("https://acme.example/", GOOD_HOME)]))
        s = inv["summary"]
        self.assertEqual(s["total"], len(inv["claims"]))
        self.assertGreaterEqual(s["machine_readable_pct"], 0)
        self.assertLessEqual(s["quotable_pct"], 100)

    def test_no_pages_is_safe(self):
        ctx = make_ctx([("https://acme.example/", GOOD_HOME)])
        ctx.pages = []
        inv = claims.build(ctx)
        self.assertEqual(inv["claims"], [])


def _report_with(ctx, consistency=None, verified=None):
    inv = claims.build(ctx)
    rpt = {
        "claims": inv,
        "consistency": consistency or {"conflicts": []},
        "knowledge_graph": {"summary": {"has_identity": True, "nodes": 3}},
        "score": {"value": 80, "discoverability": 80, "engagement": 80},
    }
    if verified is not None:
        rpt["external_verification"] = {"verified": verified}
    return rpt


class CitationReadinessTests(unittest.TestCase):
    def test_shape_and_bounds(self):
        cr = citation.build(_report_with(make_ctx([("https://acme.example/", GOOD_HOME)])))
        self.assertTrue(0 <= cr["score"] <= 100)
        self.assertEqual(len(cr["components"]), 5)
        self.assertIn(cr["grade"], list("ABCDF"))
        self.assertTrue(cr["weakest"])

    def test_contradiction_cuts_stability(self):
        rpt = _report_with(make_ctx([("https://acme.example/", GOOD_HOME)]),
                           consistency={"conflicts": [{"type": "founding_year"}]})
        stab = {c["key"]: c["value"] for c in citation.build(rpt)["components"]}["stability"]
        self.assertEqual(stab, 70)

    def test_external_verification_lifts_corroboration_and_removes_limits(self):
        rpt = _report_with(make_ctx([("https://acme.example/", GOOD_HOME)]), verified=True)
        cr = citation.build(rpt)
        cor = {c["key"]: c["value"] for c in cr["components"]}["corroboration"]
        self.assertEqual(cor, 100)
        self.assertNotIn("limits", cr)

    def test_offline_run_is_honest_about_limits(self):
        cr = citation.build(_report_with(make_ctx([("https://acme.example/", GOOD_HOME)])))
        self.assertIn("limits", cr)  # never overstates corroboration without live verification


class AnswerSimulationTests(unittest.TestCase):
    def test_one_row_per_question_with_required_fields(self):
        rows = answersim.build(_report_with(make_ctx([("https://acme.example/", GOOD_HOME)])))
        self.assertEqual(len(rows), 7)
        for r in rows:
            self.assertIn(r["answerable"], ("yes", "partial", "risky", "no"))
            self.assertIsInstance(r["would_cite"], bool)
            self.assertIn("question", r)

    def test_who_is_brand_is_answerable(self):
        rows = answersim.build(_report_with(make_ctx([("https://acme.example/", GOOD_HOME)])))
        who = next(r for r in rows if r["question"].startswith("Who is"))
        self.assertEqual(who["answerable"], "yes")

    def test_missing_fact_is_unanswerable(self):
        rows = answersim.build(_report_with(make_ctx([("https://nimbus.example/", TEXT_ONLY)])))
        loc = next(r for r in rows if "based" in r["question"])
        self.assertEqual(loc["answerable"], "no")
        self.assertFalse(loc["would_cite"])

    def test_summary_rollup(self):
        rows = answersim.build(_report_with(make_ctx([("https://acme.example/", GOOD_HOME)])))
        s = answersim.summarize(rows)
        self.assertEqual(s["questions"], 7)
        self.assertTrue(0 <= s["citable_pct"] <= 100)


class SuperlativeScanTests(unittest.TestCase):
    def test_absolute_superlatives_flagged(self):
        ctx = make_ctx([("https://zappo.example/", SUPERLATIVE_HOME)])
        block, findings = consistency.scan(ctx)
        self.assertTrue(block["unverifiable_claims"])
        self.assertTrue(any("superlative" in f.title.lower() for f in findings))

    def test_superlative_finding_is_low_severity(self):
        ctx = make_ctx([("https://zappo.example/", SUPERLATIVE_HOME)])
        _, findings = consistency.scan(ctx)
        sf = next(f for f in findings if "superlative" in f.title.lower())
        self.assertEqual(sf.severity, "low")
        self.assertEqual(sf.confidence, "low")

    def test_plain_marketing_copy_not_flagged(self):
        ctx = make_ctx([("https://acme.example/", GOOD_HOME)])
        block, findings = consistency.scan(ctx)
        self.assertEqual(block["unverifiable_claims"], [])
        self.assertFalse(any("superlative" in f.title.lower() for f in findings))


class SmartSamplingTests(unittest.TestCase):
    def test_high_value_types_rank_before_generic(self):
        rank = _page_type_rank
        self.assertLess(rank("https://x.example/about"), rank("https://x.example/blog/post"))
        self.assertLess(rank("https://x.example/contact"), rank("https://x.example/random"))
        self.assertLess(rank("https://x.example/products/a"), rank("https://x.example/z-page"))

    def test_ordering_is_deterministic(self):
        urls = ["https://x.example/z", "https://x.example/pricing",
                "https://x.example/about", "https://x.example/a-blog"]
        order = sorted(urls, key=lambda u: (_page_type_rank(u), u))
        self.assertEqual(order[0], "https://x.example/about")   # rank 0
        self.assertEqual(order[1], "https://x.example/pricing")  # rank 3
        self.assertEqual(order, sorted(urls, key=lambda u: (_page_type_rank(u), u)))  # stable


class SearchProviderTests(unittest.TestCase):
    def test_registry_is_provider_neutral(self):
        self.assertIsInstance(search_provider.for_config(make_config()), search_provider.CommonCrawlProvider)
        self.assertIsInstance(search_provider.for_config(make_config(search_provider="none")),
                              search_provider.NullProvider)
        # unknown provider degrades to the honest Null, never crashes
        self.assertIsInstance(search_provider.for_config(make_config(search_provider="acme-search")),
                              search_provider.NullProvider)

    def test_null_provider_reports_unavailable_not_guess(self):
        r = search_provider.NullProvider().corroborate("Acme", "acme.example")
        self.assertEqual(r["status"], "unavailable")

    def test_interpret_present_vs_absent(self):
        present = search_provider._interpret([{"url": "x"}], "CC-MAIN-x", "acme.example")
        absent = search_provider._interpret([], "CC-MAIN-x", "acme.example")
        self.assertEqual(present["status"], "present")
        self.assertEqual(present["records"], 1)
        self.assertEqual(absent["status"], "absent")

    def test_corpus_finding_only_on_absent(self):
        from auditlib import external
        self.assertEqual(external._corpus_findings({"status": "present"}), [])
        self.assertEqual(external._corpus_findings({"status": "unavailable"}), [])
        f = external._corpus_findings({"status": "absent", "detail": "d", "provider": "commoncrawl"})
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].severity, "low")


if __name__ == "__main__":
    unittest.main()
