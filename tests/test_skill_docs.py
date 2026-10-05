import re
import sys
import unittest

from helpers import REPO
from test_plugin_files import frontmatter

sys.path.insert(0, str(REPO / "scripts"))
import rr  # noqa: E402

SKILL = REPO / "skills" / "recursive-research"
DOCS = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
COMMANDS = set(rr.build_parser()._subparsers._group_actions[0].choices)


class SkillDocTests(unittest.TestCase):
    def test_skill_frontmatter(self):
        meta = frontmatter(SKILL / "SKILL.md")
        self.assertEqual(meta["name"], "recursive-research")
        self.assertTrue(meta["description"].startswith("Use when"))

    def test_skill_file_stays_short(self):
        lines = (SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 130, "move detail into references/ so it loads only when needed")

    def test_every_reference_mentioned_exists(self):
        mentioned = set()
        for doc in DOCS:
            mentioned |= set(re.findall(r"references/([a-z-]+\.md)", doc.read_text(encoding="utf-8")))
        existing = {p.name for p in (SKILL / "references").glob("*.md")}
        self.assertEqual(mentioned - existing, set(), "mentioned but missing")
        self.assertEqual(existing - mentioned, set(), "present but never mentioned")

    def test_stage_3_checks_the_snapshot_before_promoting_rosters(self):
        text = (SKILL / "references" / "entity-enumeration.md").read_text(encoding="utf-8")
        self.assertLess(text.index("RR check-snapshot"), text.index("RR promote-entity"),
                        "promotion writes to knowledge/, so the check must come first")

    def test_the_survey_asks_about_blocked_sections_before_assembling(self):
        text = (SKILL / "references" / "survey.md").read_text(encoding="utf-8")
        self.assertLess(text.index("RR retry-task"), text.index("complete-task <slug> assemble"))

    def test_the_skill_tells_the_user_when_a_fresh_session_is_safe(self):
        self.assertIn("fresh session", (SKILL / "SKILL.md").read_text(encoding="utf-8"))

    def test_the_loop_dispatches_from_the_brief_path(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Read your brief at", text)

    def test_being_told_to_skip_approvals_is_not_an_approval(self):
        # Pressure test B: "I trust you, skip the approvals" made the skill approve its own plan.
        skill = " ".join((SKILL / "SKILL.md").read_text(encoding="utf-8").split())
        intake = " ".join((SKILL / "references" / "intake.md").read_text(encoding="utf-8").split())
        self.assertIn("is not an approval", skill)
        self.assertIn("have not seen", skill)
        self.assertIn("skip the approvals", intake)

    def test_every_script_command_in_the_docs_is_real(self):
        for doc in DOCS:
            for command in re.findall(r"\bRR ([a-z][a-z-]*)", doc.read_text(encoding="utf-8")):
                self.assertIn(command, COMMANDS, f"{doc.name} mentions 'RR {command}'")

    def test_every_script_command_is_documented(self):
        text = "".join(doc.read_text(encoding="utf-8") for doc in DOCS)
        for command in sorted(COMMANDS):
            self.assertRegex(text, rf"\bRR {command}\b", f"'RR {command}' is never explained")


if __name__ == "__main__":
    unittest.main()
