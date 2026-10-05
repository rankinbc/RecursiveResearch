import json
import re
import unittest

from helpers import REPO
from rrlib import store, validate

SKILL = REPO / "skills" / "recursive-research"
TEMPLATES = sorted((SKILL / "templates").glob("*.md"))
DOC_TEXT = "".join(p.read_text(encoding="utf-8")
                   for p in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")])


class TemplateTests(unittest.TestCase):
    def test_every_template_mentioned_exists_and_every_template_is_used(self):
        mentioned = set(re.findall(r"templates/([a-z-]+\.md)", DOC_TEXT))
        existing = {p.name for p in TEMPLATES}
        self.assertEqual(mentioned - existing, set(), "mentioned but missing")
        self.assertEqual(existing - mentioned, set(), "present but never mentioned")

    def test_every_placeholder_is_documented_in_a_reference(self):
        documented = set(re.findall(r"\{\{([A-Z_]+)\}\}", DOC_TEXT))
        for template in TEMPLATES:
            used = set(re.findall(r"\{\{([A-Z_]+)\}\}", template.read_text(encoding="utf-8")))
            self.assertEqual(used - documented, set(), f"{template.name} uses undocumented placeholders")

    def test_research_templates_refuse_to_work_without_search(self):
        for name in ("research-entity.md", "research-deepening.md"):
            self.assertIn("SEARCH_UNAVAILABLE", (SKILL / "templates" / name).read_text(encoding="utf-8"))

    def test_deepening_template_lists_exactly_the_engines_verdicts(self):
        text = (SKILL / "templates" / "research-deepening.md").read_text(encoding="utf-8")
        listed = set(re.findall(r"^\| `([a-z]+)` \|", text, re.MULTILINE))
        self.assertEqual(listed, set(validate.VERDICTS))

    def test_the_games_example_is_a_valid_plan(self):
        example = json.loads((SKILL / "examples" / "games" / "plan-example.json").read_text(encoding="utf-8"))
        plan = store.default_plan("Example Game", "example-game")
        plan.update({k: v for k, v in example.items() if not k.startswith("_")})
        self.assertEqual(validate.validate_plan(plan), [])
        self.assertEqual(len(plan["survey_tasks"]), 20)


if __name__ == "__main__":
    unittest.main()
