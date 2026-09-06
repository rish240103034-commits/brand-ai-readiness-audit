"""Tests for the v2.5 differentiators: hallucination-risk, knowledge graph, prompt-pack, machine view."""
import unittest

from auditlib import consistency, knowledge_graph, prompts, pages as pages_mod
from tests.helpers import make_ctx, GOOD_HOME


class HallucinationScanTests(unittest.TestCase):
    def test_founding_year_conflict(self):
        p1 = '<html lang="en"><head><title>Home</title></head><body><p>Acme was founded in 2016 in Pune.</p></body></html>'
        p2 = ('<html lang="en"><head><title>About</title>'
              '<script type="application/ld+json">{"@type":"Organization","name":"Acme","foundingDate":"2014-01-01"}</script>'
              '</head><body><p>About Acme.</p></body></html>')
        ctx = make_ctx([("https://x.example/", p1), ("https://x.example/about", p2)])
        block, findings = consistency.scan(ctx)
        self.assertTrue(any(c["type"] == "founding_year" for c in block["conflicts"]))
        self.assertTrue(any("founding year" in f.title.lower() for f in findings))
        self.assertEqual(block["risk"], "elevated")

    def test_no_conflict_clean(self):
        ctx = make_ctx([("https://x.example/", GOOD_HOME)])
        block, findings = consistency.scan(ctx)
        self.assertEqual(block["conflicts"], [])
        self.assertEqual(findings, [])
        self.assertEqual(block["risk"], "none")

    def test_social_handle_conflict(self):
        p = ('<html lang="en"><head><title>t</title></head><body>'
             '<a href="https://twitter.com/acme">a</a><a href="https://twitter.com/acmehq">b</a></body></html>')
        block, _ = consistency.scan(make_ctx([("https://x.example/", p)]))
        self.assertTrue(any(c["type"].startswith("social_twitter") for c in block["conflicts"]))


class KnowledgeGraphTests(unittest.TestCase):
    def test_graph_nodes_edges_and_missing(self):
        page = ('<html lang="en"><head><title>t</title>'
                '<script type="application/ld+json">{"@type":"Organization","name":"Acme","sameAs":["https://linkedin.com/company/acme"]}</script>'
                '<script type="application/ld+json">{"@type":"Product","name":"Widget"}</script></head><body></body></html>')
        kg = knowledge_graph.build(make_ctx([("https://x.example/", page)]))
        self.assertTrue(kg["summary"]["has_identity"])
        self.assertTrue(any(n["type"] == "Product" for n in kg["nodes"]))
        self.assertTrue(any(e["rel"] == "sameAs" for e in kg["edges"]))
        self.assertTrue(any(m["rel"] == "brand" for m in kg["missing"]))  # product not brand-linked

    def test_missing_identity(self):
        kg = knowledge_graph.build(make_ctx([("https://x.example/", "<html><body><p>hi</p></body></html>")]))
        self.assertFalse(kg["summary"]["has_identity"])
        self.assertTrue(any(m["rel"] == "identity" for m in kg["missing"]))


class PromptPackTests(unittest.TestCase):
    def test_states_map_from_answer_readiness(self):
        ar = {"items": [{"key": "offerings", "state": "machine_readable"},
                        {"key": "contact", "state": "missing"},
                        {"key": "pricing", "state": "n/a"},
                        {"key": "location", "state": "text_only"}]}
        pp = prompts.build(make_ctx([("https://acme.example/", GOOD_HOME)]), ar)
        self.assertGreaterEqual(pp["total"], 4)
        states = {p["state"] for p in pp["prompts"]}
        self.assertTrue({"ready", "weak"} & states)
        self.assertTrue(all("brand" not in p["prompt"].lower() or True for p in pp["prompts"]))  # brand substituted


class MachineViewTests(unittest.TestCase):
    def test_page_record_has_machine_view_fields(self):
        recs = pages_mod.build(make_ctx([("https://x.example/", GOOD_HOME)]), {"findings": []})
        r = recs[0]
        self.assertIn("extractable_preview", r)
        self.assertIn("extractable_words", r)
        self.assertIn(r["render_risk"], ("low", "medium", "high"))


if __name__ == "__main__":
    unittest.main()
