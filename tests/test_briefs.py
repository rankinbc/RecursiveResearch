import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import REPO, SCHEMA, WorkspaceCase, proposal, raw_result
from rrlib import briefs, consolidate, scoring, store, survey, tasks

TEMPLATES = REPO / "skills" / "recursive-research" / "templates"


def text_of(info):
    return Path(info["brief"]).read_text(encoding="utf-8")


class TaskBriefTests(WorkspaceCase):
    def test_survey_brief_is_filled_for_its_own_task(self):
        self.fill_plan()
        tasks.add_session(self.ws, "survey")
        info = briefs.task_brief(self.ws, "s01")
        self.assertEqual((info["id"], info["agent"]), ("s01", "researcher"))
        text = text_of(info)
        self.assertIn("# Survey task: Overview", text)
        self.assertIn("- End to end", text)
        self.assertNotIn("- Overview", text)
        self.assertNotIn("Assemble and review", text)
        self.assertIn("- `PRIMARY`: the RFC", text)
        self.assertNotIn("EXPERT", text.split("## Provenance")[1].split("For this subject:")[1].split("Search")[0])
        self.assertIn(f"{self.ws.as_posix()}/sessions/2026-10-04_survey/raw/s01.md", text)
        self.assertNotIn("{{", text)

    def test_survey_assembly_goes_to_the_organizer(self):
        self.fill_plan()
        tasks.add_session(self.ws, "survey")
        info = briefs.task_brief(self.ws, "assemble")
        self.assertEqual(info["agent"], "organizer")
        self.assertNotIn("{{", text_of(info))

    def test_schema_brief_lists_the_expected_types(self):
        self.fill_plan()
        self.skip_to("entity_schema")
        tasks.add_session(self.ws, "entity_schema")
        info = briefs.task_brief(self.ws, "schema")
        self.assertEqual(info["agent"], "organizer")
        self.assertIn("MessageType, ErrorCode", text_of(info))
        self.assertNotIn("{{", text_of(info))

    def test_entity_brief_embeds_the_schema_of_its_own_type(self):
        self.fill_plan()
        self.skip_to("entity_enumeration")
        self.write("knowledge/entities.json", SCHEMA)
        tasks.approve(self.ws, "entity_types")
        tasks.add_session(self.ws, "entity_enumeration")
        info = briefs.task_brief(self.ws, "message_type")
        text = text_of(info)
        self.assertEqual(info["agent"], "researcher")
        self.assertIn("# Enumerate every MessageType", text)
        self.assertIn('"name": "reply"', text)
        self.assertIn('    {\n      "name": "MessageType"', text)
        self.assertNotIn("{{", text)

    def test_bootstrap_brief_goes_to_the_organizer(self):
        self.fill_plan()
        self.skip_to("deepening")
        session = tasks.add_session(self.ws, "deepening")["session"]
        info = briefs.task_brief(self.ws, "bootstrap")
        self.assertEqual(info["agent"], "organizer")
        self.assertIn(f"sessions/{session}/proposals/level_1.json", text_of(info))
        self.assertNotIn("{{", text_of(info))

    def wave(self, brief_text=None):
        session = self.start_wave([proposal("p1"), proposal("p2", branch="wire/handshake"),
                                   proposal("p3", branch="auth/tokens")])
        if brief_text is not None:
            boot = store.load_plan(self.ws)["sessions"][-2]
            self.write(f"sessions/{boot}/coordination_brief.md", brief_text)
        return session

    def test_deepening_brief_carries_only_its_own_branchs_ownership_lines(self):
        self.wave("# Who owns what\n- p1: owns framing\n- p2: owns the handshake\n- p3: owns tokens\n")
        text = text_of(briefs.task_brief(self.ws, "p1"))
        self.assertIn("**The unknown:** The maximum frame length in bytes", text)
        self.assertIn("**Branch:** `wire/framing`", text)
        self.assertIn("- p1: owns framing", text)
        self.assertIn("- p2: owns the handshake", text)
        self.assertNotIn("p3: owns tokens", text)
        self.assertNotIn("{{", text)

    def test_deepening_brief_without_a_coordination_file_says_so(self):
        self.wave()
        self.assertIn("No coordination brief was written", text_of(briefs.task_brief(self.ws, "p1")))

    def test_a_coordination_file_that_names_no_task_is_passed_whole(self):
        self.wave("Everyone stays inside their own target file.\n")
        self.assertIn("Everyone stays inside their own target file.", text_of(briefs.task_brief(self.ws, "p1")))


class JobBriefTests(WorkspaceCase):
    def test_wave_brief_knows_the_next_level_the_cap_and_closed_branches(self):
        session = self.start_wave([proposal("p1")])
        plan = store.load_plan(self.ws)
        plan["branches"]["old/branch"] = {"status": "closed", "reason": "exhausted"}
        store.save_plan(self.ws, plan)
        info = briefs.job_brief(self.ws, "wave")
        text = text_of(info)
        self.assertEqual(info["agent"], "organizer")
        self.assertIn(f"proposals/level_2.json", text)
        self.assertIn("depth cap\n  of 4", text)
        self.assertIn("closed branches: old/branch", text)
        self.assertIn(session, text)
        self.assertNotIn("{{", text)

    def test_consolidate_brief(self):
        self.start_wave([proposal("p1")])
        info = briefs.job_brief(self.ws, "consolidate")
        self.assertEqual(info["agent"], "organizer")
        self.assertNotIn("{{", text_of(info))

    def test_an_unknown_job_is_an_error(self):
        self.start_wave([proposal("p1")])
        with self.assertRaisesRegex(store.RRError, "unknown job"):
            briefs.job_brief(self.ws, "tidy")

    def test_every_template_file_is_rendered_by_some_brief(self):
        self.assertEqual({p.name for p in TEMPLATES.glob("*.md")}, set(briefs.ALL_TEMPLATES))


class AttachTests(WorkspaceCase):
    def test_a_batch_is_reduced_to_ids_agents_and_brief_paths(self):
        self.fill_plan()
        tasks.add_session(self.ws, "survey")
        batch = briefs.attach(self.ws, tasks.next_tasks(self.ws, limit=2))
        self.assertEqual([sorted(t) for t in batch["tasks"]], [["agent", "brief", "id", "output", "title"]] * 2)
        self.assertTrue(all(Path(t["brief"]).is_file() for t in batch["tasks"]))
        self.assertEqual(batch["remaining"], 4)


class AssembleSurveyTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        self.session = tasks.add_session(self.ws, "survey")["session"]
        self.write(f"sessions/{self.session}/raw/s01.md", "## Overview & Scope\n\nIt is a protocol [SECONDARY].\n")
        tasks.complete_task(self.ws, "s01", "x")
        self.write(f"sessions/{self.session}/raw/s02.md", "A section whose author forgot the heading.\n")
        tasks.complete_task(self.ws, "s02", "x")

    def test_sections_are_joined_in_order_with_contents_and_missing_list(self):
        result = survey.assemble_survey(self.ws)
        self.assertEqual((result["sections"], result["missing"]), (2, ["History"]))
        text = (self.ws / "knowledge" / "spec.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Test Subject -- Survey\n\n## Contents\n\n"))
        self.assertIn("- [Overview & Scope](#overview--scope)\n- [End to end](#end-to-end)\n", text)
        self.assertLess(text.index("It is a protocol [SECONDARY]."), text.index("## End to end\n\nA section whose"))
        self.assertTrue(text.endswith("## Missing sections\n\n- History\n"))

    def test_an_existing_survey_is_not_overwritten_without_force(self):
        survey.assemble_survey(self.ws)
        self.write("knowledge/spec.md", "edited by the organizer\n")
        with self.assertRaisesRegex(store.RRError, "already exists"):
            survey.assemble_survey(self.ws)
        self.assertEqual(survey.assemble_survey(self.ws, force=True)["sections"], 2)

    def test_nothing_to_assemble_is_an_error(self):
        store.scaffold(self.root, "Empty One")
        ws = self.root / "empty-one"
        with self.assertRaisesRegex(store.RRError, "no survey session"):
            survey.assemble_survey(ws)


class ProposalDecisionTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.session = self.start_wave([proposal("p1")])
        self.write(f"sessions/{self.session}/proposals/level_2.json", {"level": 2, "proposals": [
            proposal("a", level=2, status="proposed"), proposal("b", level=2, status="proposed"),
            proposal("c", level=2, status="proposed"), proposal("d", level=2, status="dropped")]})

    def statuses(self):
        doc = store.read_json(self.ws / "sessions" / self.session / "proposals" / "level_2.json")
        return {p["id"]: p["status"] for p in doc["proposals"]}

    def test_approve_some_and_skip_some(self):
        result = tasks.decide_proposals(self.ws, approve=["a"], skip=["b"])
        self.assertEqual((result["approved"], result["skipped"], result["proposed"]), (1, 1, 1))
        self.assertEqual(self.statuses(), {"a": "approved", "b": "skipped", "c": "proposed", "d": "dropped"})

    def test_approve_all_leaves_skipped_and_dropped_alone(self):
        result = tasks.decide_proposals(self.ws, skip=["c"], approve_all=True)
        self.assertEqual((result["approved"], result["skipped"], result["proposed"]), (2, 1, 0))
        self.assertEqual(self.statuses(), {"a": "approved", "b": "approved", "c": "skipped", "d": "dropped"})

    def test_unknown_and_dropped_ids_are_errors_and_change_nothing(self):
        with self.assertRaisesRegex(store.RRError, "no proposal"):
            tasks.decide_proposals(self.ws, approve=["a", "zzz"])
        with self.assertRaisesRegex(store.RRError, "dropped"):
            tasks.decide_proposals(self.ws, approve=["d"])
        self.assertEqual(self.statuses()["a"], "proposed")

    def test_the_gate_summary_lists_pending_proposals_compactly(self):
        self.finish(self.session, "p1", raw_result("p1"))
        gate = scoring.apply_score(self.ws, scoring.score_session(self.ws))
        self.assertEqual([p["id"] for p in gate["proposals"]], ["a", "b", "c"])
        self.assertEqual(sorted(gate["proposals"][0]),
                         ["branch", "id", "level", "sources", "status", "title", "unknown"])


class ConsolidateTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        self.write("knowledge/tree/README.md",
                   "# Tree [PRIMARY]\n\n## Known Unknowns\n- [x] solved one\n- [ ] the retry timeout\n")
        self.write("knowledge/tree/wire/README.md",
                   "# Wire\n\nMax is 9 [PRIMARY] or 12 [PRIMARY] CONFLICT\n\n- [ ] not an unknown, wrong section\n\n"
                   "## Known Unknowns\n- [ ] the frame cap\n- [ ] already recorded\n")
        self.write("knowledge/remaining_unknowns.md",
                   "# Remaining unknowns\n\n## wire\n\nClosed in w01: irreducible\n\n- already recorded\n")

    def test_open_unknowns_are_added_once_and_conflicts_are_listed(self):
        first = consolidate.consolidate(self.ws)
        self.assertEqual(first["open_unknowns"], 2)
        self.assertEqual(first["conflict_count"], 1)
        self.assertEqual((first["conflicts"][0]["file"], first["conflicts"][0]["line"]),
                         ("knowledge/tree/wire/README.md", 3))
        consolidate.consolidate(self.ws)
        text = (self.ws / "knowledge" / "remaining_unknowns.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("## Open at the end"), 1)
        self.assertEqual(text.count("the retry timeout"), 1)
        self.assertIn("- the frame cap (knowledge/tree/wire/README.md)", text)
        self.assertEqual(text.count("already recorded"), 1)
        self.assertNotIn("wrong section", text)
        self.assertIn("Closed in w01: irreducible", text)


class CompactCliTests(WorkspaceCase):
    def rr(self, *args):
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "rr.py"), "--root", str(self.root), *args],
            capture_output=True, text=True, encoding="utf-8", env={**os.environ, "RR_TODAY": "2026-10-04"})
        return proc.returncode, json.loads(proc.stdout if proc.returncode != 2 else proc.stderr)

    def test_next_task_returns_brief_paths_not_task_records(self):
        self.fill_plan()
        tasks.add_session(self.ws, "survey")
        code, out = self.rr("next-task", "test-subject", "--limit", "1")
        self.assertEqual(sorted(out["tasks"][0]), ["agent", "brief", "id", "output", "title"])
        self.assertTrue(Path(out["tasks"][0]["brief"]).is_file())

    def test_long_issue_lists_are_cut_to_ten_with_the_rest_in_a_file(self):
        self.fill_plan()
        self.skip_to("entity_enumeration")
        self.write("knowledge/entities.json", SCHEMA)
        tasks.approve(self.ws, "entity_types")
        session = tasks.add_session(self.ws, "entity_enumeration")["session"]
        entities = [{"name": f"M{i}", "properties": {"code": i, "reply": "x"}} for i in range(15)]
        self.write(f"sessions/{session}/raw/message_type.json",
                   {"entity_type": "MessageType", "count": 15, "entities": entities})
        code, out = self.rr("promote-entity", "test-subject", "message_type")
        self.assertEqual((code, out["promoted"], out["errors"], len(out["issues"])), (1, False, 30, 10))
        self.assertEqual(len(store.read_json(out["issues_file"])), 30)

    def test_job_brief_assemble_approve_and_consolidate_are_commands(self):
        self.fill_plan()
        session = tasks.add_session(self.ws, "survey")["session"]
        self.write(f"sessions/{session}/raw/s01.md", "## Overview\n\nText [PRIMARY].\n")
        tasks.complete_task(self.ws, "s01", "x")
        code, out = self.rr("assemble-survey", "test-subject")
        self.assertEqual((code, out["sections"]), (0, 1))
        code, out = self.rr("brief", "test-subject", "consolidate")
        self.assertEqual((code, out["agent"]), (0, "organizer"))
        code, out = self.rr("consolidate", "test-subject")
        self.assertEqual((code, out["conflict_count"]), (0, 0))
        code, out = self.rr("approve-proposals", "test-subject", "--all")
        self.assertEqual((code, out["approved"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
