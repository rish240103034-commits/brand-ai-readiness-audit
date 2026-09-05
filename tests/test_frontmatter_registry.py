"""Unit tests for the SKILL.md frontmatter parser and skill auto-discovery/registry."""
import unittest

from auditlib import frontmatter
from auditlib import registry


SAMPLE = """---
name: demo-skill
description: >-
  A folded multi-line
  description value.
license: MIT
allowed-tools: [Bash, Read]
metadata:
  dimension: discoverability
  checks: [crawl_render, structured_data]
---
# Body
text
"""


class FrontmatterTests(unittest.TestCase):
    def test_scalars_and_folded(self):
        fm = frontmatter.parse(SAMPLE)
        self.assertEqual(fm["name"], "demo-skill")
        self.assertEqual(fm["license"], "MIT")
        self.assertEqual(fm["description"], "A folded multi-line description value.")

    def test_inline_list(self):
        fm = frontmatter.parse(SAMPLE)
        self.assertEqual(fm["allowed-tools"], ["Bash", "Read"])

    def test_nested_mapping_and_list(self):
        fm = frontmatter.parse(SAMPLE)
        self.assertEqual(fm["metadata"]["dimension"], "discoverability")
        self.assertEqual(fm["metadata"]["checks"], ["crawl_render", "structured_data"])

    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(frontmatter.parse("# just a doc\n"), {})


class RegistryTests(unittest.TestCase):
    def test_validate_requires_name_and_description(self):
        self.assertEqual(registry.validate_skill_md({"name": "x", "description": "y"}), [])
        problems = registry.validate_skill_md({"name": "x"})
        self.assertTrue(any("description" in p for p in problems))

    def test_discovers_all_five_skills(self):
        skills = registry.discover_skills()
        ids = {s.id for s in skills}
        self.assertEqual(ids, {
            "crawl-render-audit", "structured-data-audit", "content-extractability-audit",
            "freshness-corroboration", "engagement-audit"})
        # entrypoint is excluded from the runnable set
        self.assertNotIn("audit-orchestrator", ids)

    def test_every_skill_has_bound_checks(self):
        for s in registry.discover_skills():
            self.assertTrue(s.analyze_fns, f"{s.id} has no bound checks")

    def test_select_skills_filters(self):
        skills = registry.discover_skills()
        picked = registry.select_skills(skills, ["crawl-render", "engagement-audit"])
        self.assertEqual({s.id for s in picked}, {"crawl-render-audit", "engagement-audit"})

    def test_select_unknown_is_dropped(self):
        skills = registry.discover_skills()
        self.assertEqual(registry.select_skills(skills, ["does-not-exist"]), [])


if __name__ == "__main__":
    unittest.main()
