"""The quote check applied to every part of the knowledge base, not only stage 4 results."""
import unittest

from helpers import SCHEMA, WorkspaceCase
from rrlib import store, tasks, verify

PAGE = """<html><body>
<p>A frame MUST NOT exceed 16384 bytes.</p>
<p>The reply to HELLO is WELCOME, sent with code 1.</p>
</body></html>"""


class Base(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        self.page = self.write("local/spec.html", PAGE)
        self.src = self.page.as_posix()


class MarkdownTests(Base):
    def check(self, text):
        path = self.write("knowledge/note.md", text)
        return verify.verify_markdown(self.ws, path), path.read_text(encoding="utf-8")

    def test_a_primary_tag_with_a_real_quote_is_kept(self):
        text = f'The cap is 16384 bytes [PRIMARY: "A frame MUST NOT exceed 16384 bytes." {self.src}].\n'
        result, after = self.check(text)
        self.assertEqual((result["verified"], result["downgraded"]), (1, 0))
        self.assertEqual(after, text)

    def test_a_primary_tag_whose_quote_is_not_in_the_source_is_rewritten(self):
        result, after = self.check(f'The cap is 1024 [PRIMARY: "A frame MUST NOT exceed 1024 bytes." {self.src}].\n')
        self.assertEqual((result["verified"], result["downgraded"]), (0, 1))
        self.assertEqual(after, "The cap is 1024 [SECONDARY: was PRIMARY, quote not found in source].\n")

    def test_a_bare_primary_tag_is_downgraded_because_nothing_can_be_checked(self):
        result, after = self.check("The cap is 16384 bytes [PRIMARY]. Vendors agree [SECONDARY].\n")
        self.assertEqual(result["downgraded"], 1)
        self.assertEqual(after, "The cap is 16384 bytes [SECONDARY: was PRIMARY, no quote given]. Vendors agree [SECONDARY].\n")

    def test_a_quote_may_contain_square_brackets(self):
        page = self.write("local/grammar.html", "<p>The header is name [SP value] CRLF and nothing else.</p>").as_posix()
        text = f'Header form [PRIMARY: "The header is name [SP value] CRLF and nothing else." {page}]. Next [SECONDARY].\n'
        result, after = self.check(text)
        self.assertEqual((result["verified"], result["downgraded"]), (1, 0))
        self.assertEqual(after, text)

    def test_a_failed_quote_with_square_brackets_is_replaced_whole(self):
        result, after = self.check(f'Form [PRIMARY: "The header is name [SP other] CRLF and so on." {self.src}]. Next [EXPERT].\n')
        self.assertEqual(after, "Form [SECONDARY: was PRIMARY, quote not found in source]. Next [EXPERT].\n")

    def test_a_stray_quote_mark_in_a_note_does_not_swallow_the_next_tag(self):
        text = 'Pipe [UNKNOWN: about 3" wide]. Then "quoted" words [PRIMARY].\n'
        result, after = self.check(text)
        self.assertEqual(result["downgraded"], 1)
        self.assertEqual(after, 'Pipe [UNKNOWN: about 3" wide]. Then "quoted" words [SECONDARY: was PRIMARY, no quote given].\n')

    def test_a_tag_wrapped_across_lines_is_still_read(self):
        text = f'The cap [PRIMARY: "A frame MUST NOT\nexceed 16384 bytes."\n{self.src}] holds.\n'
        result, after = self.check(text)
        self.assertEqual(result["verified"], 1)
        self.assertEqual(after, text)

    def test_other_tags_and_links_are_untouched(self):
        text = "- [ ] todo\nSee [the spec](http://x). Maybe [UNKNOWN: est 3-5]. Likely [INFERRED].\n"
        result, after = self.check(text)
        self.assertEqual((result["verified"], result["downgraded"], after), (0, 0, text))

    def test_checking_again_changes_nothing(self):
        _, first = self.check(f'A [PRIMARY]. B [PRIMARY: "A frame MUST NOT exceed 16384 bytes." {self.src}].\n')
        result = verify.verify_markdown(self.ws, self.ws / "knowledge" / "note.md")
        self.assertEqual((result["verified"], result["downgraded"]), (1, 0))
        self.assertEqual((self.ws / "knowledge" / "note.md").read_text(encoding="utf-8"), first)


class JsonLeafTests(Base):
    def test_entries_and_meta_are_checked_wherever_they_sit(self):
        path = self.write("knowledge/tree/sizes.json", {
            "_meta": {"provenance": "PRIMARY", "source": "the spec", "source_file": self.src,
                      "quote": "A frame MUST NOT exceed 16384 bytes."},
            "limits": [
                {"name": "frame", "value": 16384, "tier": "PRIMARY", "source_file": self.src,
                 "quote": "A frame MUST NOT exceed 16384 bytes."},
                {"name": "header", "value": 12, "tier": "PRIMARY", "source_file": self.src,
                 "quote": "The header is always 12 bytes long."},
                {"name": "retries", "value": 5, "tier": "OBSERVED"},
            ]})
        result = verify.verify_json(self.ws, path)
        doc = store.read_json(path)
        self.assertEqual((result["verified"], result["downgraded"]), (2, 1))
        self.assertEqual([e["tier"] for e in doc["limits"]], ["PRIMARY", "SECONDARY", "OBSERVED"])
        self.assertEqual(doc["limits"][1]["downgraded_from"], "PRIMARY")
        self.assertEqual((doc["_meta"]["provenance"], doc["_meta"]["verified"]), ("PRIMARY", True))

    def test_a_primary_meta_block_with_no_quote_is_downgraded(self):
        path = self.write("knowledge/tree/sizes.json", {"_meta": {"provenance": "PRIMARY", "source": "the spec"}})
        verify.verify_json(self.ws, path)
        meta = store.read_json(path)["_meta"]
        self.assertEqual((meta["provenance"], meta["downgraded_from"]), ("SECONDARY", "PRIMARY"))


class RosterTests(Base):
    def roster(self, **entity):
        base = {"name": "HELLO", "properties": {"code": 1, "reply": "WELCOME"}, "provenance": "PRIMARY"}
        base.update(entity)
        return self.write("knowledge/entities/message_type.json",
                          {"entity_type": "MessageType", "count": 1, "entities": [base]})

    def entity(self, path):
        return store.read_json(path)["entities"][0]

    def test_one_piece_of_evidence_can_cover_a_whole_entity(self):
        path = self.roster(evidence={"quote": "The reply to HELLO is WELCOME, sent with code 1.", "source_file": self.src})
        result = verify.verify_roster(self.ws, path)
        self.assertEqual((result["verified"], result["downgraded"]), (2, 0))
        self.assertEqual(self.entity(path)["verified"], ["code", "reply"])
        self.assertEqual(self.entity(path)["provenance"], "PRIMARY")

    def test_a_primary_value_without_evidence_is_downgraded_per_property(self):
        path = self.roster(provenance={"code": "PRIMARY", "reply": "SECONDARY"})
        result = verify.verify_roster(self.ws, path)
        e = self.entity(path)
        self.assertEqual((result["verified"], result["downgraded"]), (0, 1))
        self.assertEqual(e["provenance"], {"code": "SECONDARY", "reply": "SECONDARY"})
        self.assertIn("no quote given", e["verify_notes"]["code"])
        self.assertEqual(e["verified"], [])

    def test_a_number_must_appear_in_its_quote(self):
        path = self.roster(properties={"code": 7, "reply": "WELCOME"},
                           evidence={"quote": "The reply to HELLO is WELCOME, sent with code 1.", "source_file": self.src})
        verify.verify_roster(self.ws, path)
        e = self.entity(path)
        self.assertEqual(e["provenance"], {"code": "SECONDARY", "reply": "PRIMARY"})
        self.assertIn("does not contain the value", e["verify_notes"]["code"])

    def test_a_number_written_with_thousands_separators_or_k_is_found(self):
        page = self.write("local/pay.html", "<p>The base salary range is $150,000 - $170,000, or 1.5 times.</p>"
                                            "<p>Senior pay starts at $160K.</p>").as_posix()
        band = {"quote": "The base salary range is $150,000 - $170,000, or 1.5 times.", "source_file": page}
        path = self.roster(properties={"low": 150000, "high": 170000, "ratio": 1.5, "start": 160000, "wrong": 15},
                           evidence={"low": band, "high": band, "ratio": band, "wrong": band,
                                     "start": {"quote": "Senior pay starts at $160K.", "source_file": page}})
        verify.verify_roster(self.ws, path)
        e = self.entity(path)
        self.assertEqual(e["provenance"], {"low": "PRIMARY", "high": "PRIMARY", "ratio": "PRIMARY",
                                           "start": "PRIMARY", "wrong": "SECONDARY"})

    def test_evidence_can_be_given_per_property(self):
        path = self.roster(evidence={
            "code": {"quote": "The reply to HELLO is WELCOME, sent with code 1.", "source_file": self.src},
            "reply": {"quote": "The reply to HELLO is GOODBYE, as everyone knows.", "source_file": self.src}})
        verify.verify_roster(self.ws, path)
        self.assertEqual(self.entity(path)["provenance"], {"code": "PRIMARY", "reply": "SECONDARY"})


class SweepTests(Base):
    def test_after_a_sweep_every_primary_left_in_the_knowledge_base_is_verified(self):
        good = f'[PRIMARY: "A frame MUST NOT exceed 16384 bytes." {self.src}]'
        self.write("knowledge/spec.md", f"# Survey\n\nCap {good}. Also fast [PRIMARY].\n")
        self.write("knowledge/tree/README.md", f"# Tree\n\nCap {good}.\n\n## Known Unknowns\n- none\n")
        self.write("knowledge/tree/sizes.json", {"_meta": {"provenance": "PRIMARY", "source": "x"}})
        self.write("knowledge/entities/message_type.json", {"entity_type": "MessageType", "count": 1, "entities": [
            {"name": "HELLO", "properties": {"code": 1, "reply": "WELCOME"}, "provenance": "PRIMARY"}]})
        result = verify.sweep(self.ws)
        self.assertEqual((result["files_checked"], result["verified"], result["downgraded"]), (4, 2, 4))
        self.assertNotIn("[PRIMARY]", (self.ws / "knowledge" / "spec.md").read_text(encoding="utf-8"))
        ledger = store.read_json(self.ws / "knowledge" / "verification.json")["files"]
        self.assertEqual(sorted(ledger), ["knowledge/entities/message_type.json", "knowledge/spec.md",
                                          "knowledge/tree/README.md", "knowledge/tree/sizes.json"])
        self.assertEqual(ledger["knowledge/spec.md"]["verified"], 1)

    def test_unchanged_files_are_not_checked_again_and_changed_ones_are(self):
        self.write("knowledge/spec.md", "# Survey\n\nFast [PRIMARY].\n")
        verify.sweep(self.ws)
        again = verify.sweep(self.ws)
        self.assertEqual((again["files_checked"], again["downgraded"]), (0, 0))
        self.write("knowledge/spec.md", "# Survey\n\nFast [SECONDARY]. New [PRIMARY].\n")
        third = verify.sweep(self.ws)
        self.assertEqual((third["files_checked"], third["downgraded"]), (1, 1))

    def test_is_checked_tells_swept_files_from_edited_ones(self):
        path = self.write("knowledge/spec.md", "# Survey\n")
        self.assertFalse(verify.is_checked(self.ws, path))
        verify.sweep(self.ws)
        self.assertTrue(verify.is_checked(self.ws, path))
        self.write("knowledge/spec.md", "# Survey, edited\n")
        self.assertFalse(verify.is_checked(self.ws, path))


class WiringTests(Base):
    def test_a_survey_section_is_checked_when_its_task_completes(self):
        session = tasks.add_session(self.ws, "survey")["session"]
        self.write(f"sessions/{session}/raw/s01.md", "## Overview\n\nFast [PRIMARY]. Old [SECONDARY].\n")
        result = tasks.complete_task(self.ws, "s01", "wrote it")
        self.assertEqual((result["quotes_verified"], result["quotes_downgraded"]), (0, 1))
        raw = (self.ws / "sessions" / session / "raw" / "s01.md").read_text(encoding="utf-8")
        self.assertIn("[SECONDARY: was PRIMARY, no quote given]", raw)

    def test_a_promoted_roster_is_checked_and_recorded(self):
        self.skip_to("entity_enumeration")
        self.write("knowledge/entities.json", SCHEMA)
        tasks.approve(self.ws, "entity_types")
        session = tasks.add_session(self.ws, "entity_enumeration")["session"]
        self.write(f"sessions/{session}/raw/message_type.json", {"entity_type": "MessageType", "count": 1, "entities": [
            {"name": "HELLO", "properties": {"code": 1, "reply": "WELCOME"}, "provenance": "PRIMARY",
             "evidence": {"quote": "The reply to HELLO is WELCOME, sent with code 1.", "source_file": self.src}}]})
        result = tasks.promote_entity(self.ws, "message_type")
        self.assertEqual((result["promoted"], result["quotes_verified"], result["quotes_downgraded"]), (True, 2, 0))
        self.assertTrue(verify.is_checked(self.ws, self.ws / "knowledge" / "entities" / "message_type.json"))

    def test_fetched_pages_are_kept_once_for_the_whole_workspace(self):
        real = verify.FETCH
        self.addCleanup(setattr, verify, "FETCH", real)
        calls = []
        verify.FETCH = lambda url: calls.append(url) or PAGE
        tag = '[PRIMARY: "A frame MUST NOT exceed 16384 bytes." https://example.org/spec]'
        self.write("knowledge/spec.md", f"A {tag}.\n")
        self.write("knowledge/tree/README.md", f"B {tag}.\n\n## Known Unknowns\n- none\n")
        verify.sweep(self.ws)
        self.assertEqual(calls, ["https://example.org/spec"])
        self.assertEqual(len(list((self.ws / "sources").glob("*.txt"))), 1)


if __name__ == "__main__":
    unittest.main()
