import unittest

from helpers import SCHEMA, WorkspaceCase, proposal, raw_result
from rrlib import store, tasks


class ApprovalTests(WorkspaceCase):
    def test_no_session_may_start_before_the_plan_is_approved(self):
        self.fill_plan(approve=False)
        with self.assertRaisesRegex(store.RRError, "not approved"):
            tasks.add_session(self.ws, "survey")

    def test_stages_run_in_order(self):
        self.fill_plan()
        with self.assertRaisesRegex(store.RRError, "survey stage is not done yet"):
            tasks.add_session(self.ws, "entity_schema")
        with self.assertRaisesRegex(store.RRError, "survey stage is not done yet"):
            tasks.add_session(self.ws, "deepening")

    def test_an_incomplete_plan_cannot_be_approved(self):
        with self.assertRaisesRegex(store.RRError, "cannot approve plan"):
            tasks.approve(self.ws, "plan")
        self.assertFalse(store.load_plan(self.ws)["approvals"]["plan"])

    def test_enumeration_waits_for_entity_type_approval(self):
        self.fill_plan()
        self.skip_to("entity_enumeration")
        self.write("knowledge/entities.json", SCHEMA)
        with self.assertRaisesRegex(store.RRError, "entity type list is not approved"):
            tasks.add_session(self.ws, "entity_enumeration")
        tasks.approve(self.ws, "entity_types")
        result = tasks.add_session(self.ws, "entity_enumeration")
        self.assertEqual(result["task_count"], 1)
        task = tasks.next_tasks(self.ws)["tasks"][0]
        self.assertEqual(task["id"], "message_type")
        self.assertEqual(task["output"], "sessions/2026-10-04_entity_enumeration/raw/message_type.json")


class SurveyTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        self.session = tasks.add_session(self.ws, "survey")["session"]

    def test_survey_session_has_plan_tasks_plus_assembly(self):
        self.assertEqual(self.session, "2026-10-04_survey")
        doc = tasks.load_tasks(self.ws, self.session)
        self.assertEqual([t["id"] for t in doc["tasks"]], ["s01", "s02", "s03", "assemble"])
        self.assertEqual(doc["tasks"][0]["output"], "sessions/2026-10-04_survey/raw/s01.md")
        self.assertEqual(doc["tasks"][-1]["output"], "knowledge/spec.md")
        plan = store.load_plan(self.ws)
        self.assertEqual(plan["sessions"], [self.session])
        self.assertEqual(plan["stages"]["survey"], "in_progress")
        self.assertTrue((self.ws / "sessions" / self.session / "raw").is_dir())

    def test_the_same_session_cannot_be_created_twice(self):
        with self.assertRaisesRegex(store.RRError, "already exists"):
            tasks.add_session(self.ws, "survey")

    def test_batch_respects_the_limit_and_never_includes_the_solo_task(self):
        self.assertEqual([t["id"] for t in tasks.next_tasks(self.ws, limit=2)["tasks"]], ["s01", "s02"])
        self.assertEqual([t["id"] for t in tasks.next_tasks(self.ws)["tasks"]], ["s01", "s02", "s03"])
        with self.assertRaises(store.RRError):
            tasks.next_tasks(self.ws, limit=0)

    def test_the_solo_task_is_handed_out_alone_once_the_rest_are_done(self):
        for tid in ("s01", "s02", "s03"):
            self.write(f"sessions/{self.session}/raw/{tid}.md", "section\n")
            tasks.complete_task(self.ws, tid, "wrote section")
        batch = tasks.next_tasks(self.ws)
        self.assertEqual([t["id"] for t in batch["tasks"]], ["assemble"])
        self.assertEqual(batch["remaining"], 1)
        self.assertFalse(batch["complete"])

    def test_a_task_without_output_cannot_be_completed(self):
        with self.assertRaisesRegex(store.RRError, "produced nothing"):
            tasks.complete_task(self.ws, "s01", "claimed")
        self.write(f"sessions/{self.session}/raw/s01.md", "")
        with self.assertRaisesRegex(store.RRError, "produced nothing"):
            tasks.complete_task(self.ws, "s01", "claimed")
        self.assertFalse(tasks.load_tasks(self.ws, self.session)["tasks"][0]["passes"])

    def test_completing_logs_activity_and_refuses_a_second_time(self):
        self.write(f"sessions/{self.session}/raw/s01.md", "section\n")
        result = tasks.complete_task(self.ws, "s01", "wrote the overview")
        self.assertEqual(result, {"completed": "s01", "verdict": None, "remaining": 3})
        log = (self.ws / "sessions" / self.session / "activity.md").read_text(encoding="utf-8")
        self.assertIn("- 2026-10-04 s01: wrote the overview\n", log)
        with self.assertRaisesRegex(store.RRError, "already complete"):
            tasks.complete_task(self.ws, "s01", "again")
        with self.assertRaisesRegex(store.RRError, "no task"):
            tasks.complete_task(self.ws, "s99", "ghost")

    def test_a_task_is_retried_once_and_then_blocked(self):
        first = tasks.fail_task(self.ws, "s01", "search timed out")
        self.assertEqual(first, {"failed": "s01", "attempts": 1, "blocked": False})
        self.assertEqual(tasks.next_tasks(self.ws, limit=1)["tasks"][0]["id"], "s01")
        second = tasks.fail_task(self.ws, "s01", "search timed out again")
        self.assertTrue(second["blocked"])
        batch = tasks.next_tasks(self.ws)
        self.assertEqual([t["id"] for t in batch["tasks"]], ["s02", "s03"])
        self.assertEqual(batch["blocked"], [{"id": "s01", "last_error": "search timed out again"}])
        self.assertEqual(batch["remaining"], 4)


class DeepeningTests(WorkspaceCase):
    def test_first_deepening_session_is_the_bootstrap(self):
        self.fill_plan()
        self.skip_to("deepening")
        result = tasks.add_session(self.ws, "deepening")
        self.assertEqual(result["session"], "2026-10-04_deepening_w00")
        self.assertEqual(tasks.next_tasks(self.ws)["tasks"][0]["id"], "bootstrap")

    def test_a_wave_is_built_from_approved_proposals_only(self):
        session = self.start_wave([proposal("p1"), proposal("p2", status="proposed"),
                                   proposal("p3", status="skipped")])
        self.assertEqual(session, "2026-10-04_deepening_w01")
        task = tasks.load_tasks(self.ws, session)["tasks"]
        self.assertEqual([t["id"] for t in task], ["p1"])
        self.assertEqual(task[0]["branch"], "wire/framing")
        self.assertEqual(task[0]["level"], 1)
        self.assertEqual(task[0]["unknown"], "The maximum frame length in bytes")
        self.assertEqual(task[0]["output"], f"sessions/{session}/raw/p1.json")

    def test_a_wave_needs_at_least_one_approved_proposal(self):
        with self.assertRaisesRegex(store.RRError, "no approved proposals"):
            self.start_wave([proposal("p1", status="proposed")])

    def test_invalid_proposals_block_the_wave(self):
        with self.assertRaisesRegex(store.RRError, "invalid proposals"):
            self.start_wave([proposal("p1", unknown_being_resolved="Research this further")])

    def test_completing_a_research_task_records_its_verdict(self):
        session = self.start_wave([proposal("p1")])
        self.write(f"sessions/{session}/raw/p1.json", raw_result("p1", "irreducible"))
        self.assertEqual(tasks.complete_task(self.ws, "p1", "searched")["verdict"], "irreducible")

    def test_an_invalid_research_result_cannot_be_completed(self):
        session = self.start_wave([proposal("p1")])
        self.write(f"sessions/{session}/raw/p1.json", raw_result("p1", "irreducible", sources_searched=[]))
        with self.assertRaisesRegex(store.RRError, "not a valid result"):
            tasks.complete_task(self.ws, "p1", "searched")


class PromoteTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        self.skip_to("entity_enumeration")
        self.write("knowledge/entities.json", SCHEMA)
        tasks.approve(self.ws, "entity_types")
        self.session = tasks.add_session(self.ws, "entity_enumeration")["session"]

    def roster(self, provenance):
        return {"entity_type": "MessageType", "count": 1, "entities": [
            {"name": "HELLO", "properties": {"code": 1, "reply": "WELCOME"}, "provenance": provenance}]}

    def test_a_valid_roster_is_copied_into_knowledge(self):
        self.write(f"sessions/{self.session}/raw/message_type.json", self.roster("PRIMARY"))
        result = tasks.promote_entity(self.ws, "message_type")
        self.assertTrue(result["promoted"])
        self.assertTrue((self.ws / "knowledge/entities/message_type.json").is_file())

    def test_an_untagged_roster_is_not_copied(self):
        self.write(f"sessions/{self.session}/raw/message_type.json", self.roster(None))
        result = tasks.promote_entity(self.ws, "message_type")
        self.assertFalse(result["promoted"])
        self.assertEqual(len(result["issues"]), 2)
        self.assertFalse((self.ws / "knowledge/entities/message_type.json").exists())


if __name__ == "__main__":
    unittest.main()
