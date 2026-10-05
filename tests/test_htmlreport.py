import json
import os
import re
import subprocess
import sys
import unittest

from helpers import REPO, WorkspaceCase
from rrlib import htmlreport, mdlite, store, verify

PAGE = "<p>A frame MUST NOT exceed 16384 bytes.</p><p>The reply to HELLO is WELCOME, sent with code 1.</p>"


class MarkdownTests(unittest.TestCase):
    def html(self, text, checked=True):
        return mdlite.render(text, checked=checked)

    def test_headings_paragraphs_and_emphasis(self):
        out = self.html("# Title\n\nSome **bold** and *soft* text\non two lines.\n\n## Part two\n")
        self.assertIn("<h1", out)
        self.assertIn(">Title</h1>", out)
        self.assertIn("<p>Some <strong>bold</strong> and <em>soft</em> text on two lines.</p>", out)
        self.assertIn('<h2 id="part-two">Part two</h2>', out)

    def test_lists_with_checkboxes(self):
        out = self.html("- [x] done thing\n- [ ] open thing\n- plain\n\n1. first\n2. second\n")
        self.assertIn('<li class="done"><span class="box">✓</span>done thing</li>', out)
        self.assertIn('<li class="open"><span class="box"></span>open thing</li>', out)
        self.assertIn("<li>plain</li>", out)
        self.assertIn("<ol><li>first</li><li>second</li></ol>", out)

    def test_tables_and_code(self):
        out = self.html("| Code | Meaning |\n|---|---|\n| 20 | `OK` |\n\n    indented code <b>\n\n```\nfenced & raw\n```\n")
        self.assertIn("<table><thead><tr><th>Code</th><th>Meaning</th></tr></thead>", out)
        self.assertIn("<td>20</td><td><code>OK</code></td>", out)
        self.assertIn("<pre><code>indented code &lt;b&gt;</code></pre>", out)
        self.assertIn("<pre><code>fenced &amp; raw</code></pre>", out)

    def test_everything_from_the_knowledge_base_is_escaped(self):
        out = self.html('Hello <script>alert(1)</script> and <img src=x onerror=y>\n\n[bad](javascript:alert(1))\n')
        self.assertNotIn("<script", out)
        self.assertNotIn("<img", out)
        self.assertNotIn("javascript:", out)
        self.assertIn("&lt;script&gt;", out)

    def test_only_web_links_become_links(self):
        out = self.html("See [the spec](https://example.org/a?b=1&c=2) and [a file](../other/README.md).\n")
        self.assertIn('<a href="https://example.org/a?b=1&amp;c=2" rel="noopener noreferrer">the spec</a>', out)
        self.assertNotIn("../other", out)
        self.assertIn("a file", out)

    def test_plain_tier_tags_become_badges(self):
        out = self.html("Vendors agree [SECONDARY]. Maybe [UNKNOWN: est 3-5]. Guess [INFERRED].\n")
        self.assertIn('<span class="tier t-secondary">SECONDARY</span>', out)
        self.assertIn('<span class="tier t-unknown" title="est 3-5">UNKNOWN</span>', out)
        self.assertIn('<span class="tier t-inferred">INFERRED</span>', out)

    def test_a_verified_primary_tag_links_to_its_source_and_shows_the_quote(self):
        out = self.html('Cap [PRIMARY: "A frame MUST NOT exceed 16384 bytes." https://example.org/spec].\n')
        self.assertIn('<a class="tier t-primary verified" href="https://example.org/spec" rel="noopener noreferrer" '
                      'title="“A frame MUST NOT exceed 16384 bytes.”">PRIMARY ✓</a>', out)

    def test_primary_in_an_unchecked_file_is_not_shown_as_verified(self):
        out = self.html('Cap [PRIMARY: "A frame MUST NOT exceed 16384 bytes." https://example.org/spec].\n', checked=False)
        self.assertNotIn("verified", out)
        self.assertNotIn("✓", out)
        self.assertIn('class="tier t-primary unchecked"', out)

    def test_a_downgraded_tag_says_why_and_conflicts_stand_out(self):
        out = self.html("Cap [SECONDARY: was PRIMARY, quote not found in source]. Max 9 or 12 CONFLICT\n")
        self.assertIn('<span class="tier t-secondary" title="was PRIMARY, quote not found in source">SECONDARY</span>', out)
        self.assertIn('<span class="conflict">CONFLICT</span>', out)


class ReportTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        src = self.write("local/spec.html", PAGE).as_posix()
        good = f'[PRIMARY: "A frame MUST NOT exceed 16384 bytes." {src}]'
        self.write("knowledge/spec.md", f"# Survey\n\n## Overview\n\nCap {good}. Vendors agree [SECONDARY].\n")
        self.write("knowledge/tree/README.md", "# Wire protocol\n\nOverview [SECONDARY].\n\n## Known Unknowns\n- none\n")
        self.write("knowledge/tree/wire/README.md",
                   f"# Wire\n\nCap {good}. Max 9 [EXPERT] or 12 [EXPERT] CONFLICT\n\n"
                   "## Known Unknowns\n- [x] The frame cap\n- [ ] The retry timeout\n")
        self.write("knowledge/tree/wire/frame_sizes.json", {
            "_meta": {"provenance": "SECONDARY", "source": "vendor docs <b>"},
            "limits": [{"name": "frame", "value": 16384, "tier": "PRIMARY", "source_file": src,
                        "quote": "A frame MUST NOT exceed 16384 bytes."},
                       {"name": "header <script>x</script>", "value": 12, "tier": "SECONDARY"}],
            "unit": "bytes"})
        self.write("knowledge/entities.json", {"entity_types": [{"name": "MessageType", "description": "A kind of message",
                   "properties": [{"name": "code"}, {"name": "reply"}]}]})
        self.write("knowledge/entities/message_type.json", {"entity_type": "MessageType", "count": 2, "entities": [
            {"name": "HELLO", "properties": {"code": 1, "reply": "WELCOME"}, "provenance": "PRIMARY",
             "evidence": {"quote": "The reply to HELLO is WELCOME, sent with code 1.", "source_url": "https://example.org/spec"}},
            {"name": "PING", "properties": {"code": 2, "reply": None},
             "provenance": {"code": "SECONDARY", "reply": "UNKNOWN"}}]})
        self.write("knowledge/remaining_unknowns.md", "# Remaining unknowns\n\n## wire\n\nClosed in w01: irreducible\n\n- the retry timeout\n")
        plan = store.load_plan(self.ws)
        plan["branches"] = {"wire": {"status": "closed", "reason": "irreducible", "level": 1}}
        store.save_plan(self.ws, plan)
        real = verify.FETCH
        self.addCleanup(setattr, verify, "FETCH", real)
        verify.FETCH = lambda url: PAGE
        verify.sweep(self.ws)
        self.result = htmlreport.write_report(self.ws)
        self.html = (self.ws / "report.html").read_text(encoding="utf-8")

    def test_it_writes_one_self_contained_file(self):
        self.assertEqual(self.result["file"], (self.ws / "report.html").as_posix())
        self.assertTrue(self.html.startswith("<!doctype html>"))
        self.assertNotRegex(self.html, r"<(script|link|img|iframe)[^>]+(src|href)=")
        self.assertNotIn("@import", self.html)
        self.assertNotIn("url(", self.html)

    def test_it_states_the_subject_goal_and_headline_numbers(self):
        self.assertIn("<title>Test Subject</title>", self.html)
        self.assertIn("Rebuild the protocol from the notes alone", self.html)
        card = self.result["scorecard"]
        self.assertEqual((card["claims"], card["verified"], card["unknowns_open"], card["conflicts"]), (12, 5, 1, 1))
        for label, value in (("Claims", 12), ("Verified at source", 5), ("Open unknowns", 1), ("Conflicts", 1)):
            self.assertRegex(self.html, rf'<div class="num">{value}</div>\s*<div class="label">{label}</div>')

    def test_every_part_of_the_knowledge_base_is_there(self):
        for needle in ('id="scorecard"', 'id="conflicts"', 'id="tree"', 'id="catalogue"', 'id="survey"',
                       'id="unknowns"', ">Wire</h", "frame_sizes.json", ">MessageType<", "the retry timeout",
                       "irreducible"):
            self.assertIn(needle, self.html, needle)

    def test_verified_claims_link_to_their_source_everywhere(self):
        self.assertGreaterEqual(self.html.count("PRIMARY ✓"), 3)
        self.assertIn('href="https://example.org/spec"', self.html)
        self.assertIn("“The reply to HELLO is WELCOME, sent with code 1.”", self.html)

    def test_catalogue_cells_carry_their_tier(self):
        self.assertRegex(self.html, r'<td[^>]*class="[^"]*t-primary[^"]*"[^>]*>.*?WELCOME')
        self.assertRegex(self.html, r'<td[^>]*class="[^"]*t-unknown[^"]*"')

    def test_content_from_the_knowledge_base_cannot_inject_markup(self):
        self.assertNotIn("<script>x</script>", self.html)
        self.assertIn("header &lt;script&gt;x&lt;/script&gt;", self.html)
        self.assertIn("vendor docs &lt;b&gt;", self.html)
        self.assertEqual(len(re.findall(r"<script\b", self.html)), 1, "only the report's own script")

    def test_local_source_paths_are_not_turned_into_links(self):
        self.assertNotIn('href="C:', self.html)
        self.assertNotIn('href="/', self.html)

    def test_the_command_writes_the_report(self):
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "rr.py"), "--root", str(self.root),
                               "report", "test-subject"], capture_output=True, text=True, encoding="utf-8",
                              env={**os.environ, "RR_TODAY": "2026-10-04"})
        out = json.loads(proc.stdout)
        self.assertEqual((proc.returncode, out["file"]), (0, (self.ws / "report.html").as_posix()))
        self.assertEqual(out["scorecard"]["claims"], 12)

    def test_an_empty_workspace_still_produces_a_report(self):
        ws = store.scaffold(self.root, "Empty One")["workspace"]
        result = htmlreport.write_report(ws)
        self.assertEqual(result["scorecard"]["claims"], 0)
        self.assertIn("No research yet", (self.root / "empty-one" / "report.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
