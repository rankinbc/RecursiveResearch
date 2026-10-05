import unittest

from helpers import WorkspaceCase
from rrlib import progress, scorecard, store, verify

PAGE = "<p>A frame MUST NOT exceed 16384 bytes.</p><p>The reply to HELLO is WELCOME, sent with code 1.</p>"


class ScorecardTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        src = self.write("local/spec.html", PAGE).as_posix()
        good = f'[PRIMARY: "A frame MUST NOT exceed 16384 bytes." {src}]'
        self.write("knowledge/spec.md", f"# Survey\n\nCap {good}. Vendors agree [SECONDARY]. Fast [PRIMARY].\n")
        self.write("knowledge/tree/README.md", "# Tree\n\nOverview [SECONDARY].\n\n## Known Unknowns\n- none\n")
        self.write("knowledge/tree/wire/README.md",
                   f"# Wire\n\nCap {good}. Probably padded [INFERRED]. Max 9 [EXPERT] or 12 [EXPERT] CONFLICT\n\n"
                   "## Known Unknowns\n- [x] The frame cap\n- [ ] The retry timeout\n- [ ] The backoff multiplier\n")
        self.write("knowledge/tree/wire/framing/README.md", "# Framing\n\nSeen once [OBSERVED].\n\n## Known Unknowns\n- none\n")
        self.write("knowledge/tree/wire/framing/sizes.json", {
            "_meta": {"provenance": "SECONDARY", "source": "vendor docs"},
            "limits": [{"name": "frame", "value": 16384, "tier": "PRIMARY", "source_file": src,
                        "quote": "A frame MUST NOT exceed 16384 bytes."},
                       {"name": "header", "value": 12, "tier": "SECONDARY"}]})
        self.write("knowledge/tree/auth/README.md", "# Auth\n\nNothing yet.\n\n## Known Unknowns\n- [ ] The token format\n")
        self.write("knowledge/entities.json", {"entity_types": [{"name": "MessageType", "description": "d",
                   "properties": [{"name": "code"}, {"name": "reply"}]}]})
        self.write("knowledge/entities/message_type.json", {"entity_type": "MessageType", "count": 2, "entities": [
            {"name": "HELLO", "properties": {"code": 1, "reply": "WELCOME"}, "provenance": "PRIMARY",
             "evidence": {"quote": "The reply to HELLO is WELCOME, sent with code 1.", "source_file": src}},
            {"name": "PING", "properties": {"code": 2, "reply": None},
             "provenance": {"code": "SECONDARY", "reply": "UNKNOWN"}}]})
        plan = store.load_plan(self.ws)
        plan["branches"] = {"wire": {"status": "open", "level": 1},
                            "wire/framing": {"status": "closed", "reason": "exhausted", "level": 2}}
        store.save_plan(self.ws, plan)
        verify.sweep(self.ws)
        self.card = scorecard.scorecard(self.ws)

    def test_the_survey_counts_its_tags_and_what_was_verified(self):
        s = self.card["survey"]
        self.assertEqual((s["tiers"]["PRIMARY"], s["tiers"]["SECONDARY"], s["verified"]), (1, 2, 1))
        self.assertEqual(s["claims"], 3)

    def test_the_catalogue_counts_values_per_type(self):
        (t,) = self.card["catalogue"]
        self.assertEqual((t["name"], t["instances"], t["claims"]), ("MessageType", 2, 4))
        self.assertEqual((t["tiers"]["PRIMARY"], t["tiers"]["SECONDARY"], t["tiers"]["UNKNOWN"], t["verified"]),
                         (2, 1, 1, 2))

    def test_branches_roll_up_their_sub_folders(self):
        by = {b["branch"]: b for b in self.card["branches"]}
        self.assertEqual(sorted(by), ["(overview)", "auth", "wire"])
        wire = by["wire"]
        self.assertEqual((wire["tiers"]["PRIMARY"], wire["verified"]), (2, 2))
        self.assertEqual((wire["tiers"]["EXPERT"], wire["tiers"]["INFERRED"], wire["tiers"]["OBSERVED"],
                          wire["tiers"]["SECONDARY"]), (2, 1, 1, 1))
        self.assertEqual((wire["unknowns_open"], wire["unknowns_resolved"], wire["conflicts"]), (2, 1, 1))
        self.assertEqual((wire["status"], wire["depth"], wire["files"]), ("open", 2, 3))
        self.assertEqual(wire["closed"], [{"branch": "wire/framing", "reason": "exhausted"}])

    def test_a_branch_no_wave_has_touched_is_not_started(self):
        auth = {b["branch"]: b for b in self.card["branches"]}["auth"]
        self.assertEqual((auth["status"], auth["claims"], auth["unknowns_open"]), ("not started", 0, 1))

    def test_overall_adds_everything_up(self):
        o = self.card["overall"]
        self.assertEqual(o["claims"], 3 + 4 + 8)
        self.assertEqual((o["tiers"]["PRIMARY"], o["verified"], o["unverified_primary"]), (5, 5, 0))
        self.assertEqual((o["unknowns_open"], o["conflicts"]), (3, 1))
        self.assertEqual(o["verified_share"], round(5 / 15, 3))

    def test_primary_in_a_file_edited_since_the_check_is_not_called_verified(self):
        self.write("knowledge/spec.md", "# Survey\n\nNew and unchecked [PRIMARY].\n")
        card = scorecard.scorecard(self.ws)
        self.assertEqual((card["survey"]["tiers"]["PRIMARY"], card["survey"]["verified"]), (1, 0))
        self.assertEqual(card["overall"]["unverified_primary"], 1)

    def test_an_empty_workspace_scores_as_zero(self):
        ws = store.scaffold(self.root, "Empty")["workspace"]
        card = scorecard.scorecard(ws)
        self.assertEqual((card["overall"]["claims"], card["overall"]["verified_share"]), (0, 0.0))
        self.assertEqual((card["branches"], card["catalogue"]), ([], []))

    def test_the_progress_view_shows_the_knowledge_line(self):
        text = progress.render(progress.progress(self.ws))
        self.assertIn("Knowledge", text)
        self.assertRegex(text, r"claims 15\s+verified 5")
        self.assertRegex(text, r"open unknowns 3\s+conflicts 1")


if __name__ == "__main__":
    unittest.main()
