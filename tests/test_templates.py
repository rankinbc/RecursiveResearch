import json
import re
import unittest

from helpers import REPO
from rrlib import store, validate

SKILL = REPO / "skills" / "recursive-research"
DOC_TEXT = "".join(p.read_text(encoding="utf-8")
                   for p in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")])


def template(name):
    return (SKILL / "templates" / name).read_text(encoding="utf-8")


class TemplateTests(unittest.TestCase):
    def test_the_coordinator_is_never_told_to_fill_a_template_by_hand(self):
        self.assertNotIn("{{", DOC_TEXT, "briefs are rendered by the script; the documents should not list placeholders")
        self.assertNotRegex(DOC_TEXT, r"templates/[a-z-]+\.md")

    def test_research_templates_refuse_to_work_without_search(self):
        for name in ("research-entity.md", "research-deepening.md"):
            self.assertIn("SEARCH_UNAVAILABLE", template(name))

    def test_deepening_template_lists_exactly_the_engines_verdicts(self):
        listed = set(re.findall(r"^\| `([a-z]+)` \|", template("research-deepening.md"), re.MULTILINE))
        self.assertEqual(listed, set(validate.VERDICTS))

    def test_agents_are_not_invited_to_read_whole_large_files(self):
        self.assertIn("Do not read the whole file", template("research-entity.md"))
        self.assertIn("Do not open the roster files", template("organize-bootstrap.md"))

    def test_the_survey_organizer_edits_instead_of_rewriting(self):
        text = template("organize-survey.md")
        self.assertIn("already been assembled", text)
        self.assertIn("Do not rewrite the file", text)

    def test_consolidation_leaves_mechanical_listing_to_the_script(self):
        text = template("organize-consolidate.md")
        self.assertNotIn("Open at the end", text)
        self.assertNotIn("Search the tree for lines marked", text)

    def test_the_games_example_is_a_valid_plan(self):
        example = json.loads((SKILL / "examples" / "games" / "plan-example.json").read_text(encoding="utf-8"))
        plan = store.default_plan("Example Game", "example-game")
        plan.update({k: v for k, v in example.items() if not k.startswith("_")})
        self.assertEqual(validate.validate_plan(plan), [])
        self.assertEqual(len(plan["survey_tasks"]), 20)


if __name__ == "__main__":
    unittest.main()
