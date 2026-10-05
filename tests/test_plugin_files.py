import json
import unittest

from helpers import REPO


def frontmatter(path):
    """Parse the simple 'key: value' block between the first two '---' lines."""
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---", f"{path.name} must start with frontmatter"
    end = lines.index("---", 1)
    return dict(line.split(": ", 1) for line in lines[1:end])


def tools(path):
    return {t.strip() for t in frontmatter(path)["tools"].split(",")}


class PluginFileTests(unittest.TestCase):
    def test_manifest_names_the_plugin(self):
        manifest = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "recursive-research")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue(manifest["description"])

    def test_agents_are_named_after_their_files(self):
        for name in ("researcher", "organizer"):
            meta = frontmatter(REPO / "agents" / f"{name}.md")
            self.assertEqual(meta["name"], name)
            self.assertTrue(meta["description"])

    def test_researcher_is_told_what_a_summarizing_fetch_can_claim(self):
        text = (REPO / "agents" / "researcher.md").read_text(encoding="utf-8")
        self.assertIn("at most `SECONDARY`", text)

    def test_researcher_can_search_but_cannot_edit_or_run_commands(self):
        self.assertEqual(tools(REPO / "agents" / "researcher.md"),
                         {"Read", "Glob", "Grep", "WebSearch", "WebFetch", "Write"})

    def test_organizer_can_edit_but_cannot_search_or_run_commands(self):
        self.assertEqual(tools(REPO / "agents" / "organizer.md"),
                         {"Read", "Glob", "Grep", "Write", "Edit"})


if __name__ == "__main__":
    unittest.main()
