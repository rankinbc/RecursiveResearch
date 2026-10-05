import unittest

from helpers import WorkspaceCase, proposal, raw_result
from rrlib import report, scoring, store, tasks


class ScoreTests(WorkspaceCase):
    def one_task(self, raw_kwargs=None, dispositions=None, level=1, verdict="continue", tiers=None):
        session = self.start_wave([proposal("p1", level=level)])
        tiers = ("PRIMARY", "PRIMARY", "PRIMARY") if tiers is None else tiers
        self.finish(session, "p1", raw_result("p1", verdict, tiers, **(raw_kwargs or {})), dispositions)
        return scoring.score_session(self.ws)["branches"]["wire/framing"]

    def test_a_productive_branch_stays_open(self):
        b = self.one_task()
        self.assertEqual((b["recommendation"], b["reason"]), ("open", ""))
        self.assertEqual((b["findings"], b["new"], b["unknowns_resolved"]), (3, 3, 1))

    def test_verdicts_without_continue_close_the_branch(self):
        for verdict in ("exhausted", "irreducible", "sufficient"):
            with self.subTest(verdict):
                self.setUp()
                b = self.one_task(verdict=verdict)
                self.assertEqual((b["recommendation"], b["reason"]), ("close", verdict))

    def test_few_new_facts_close_the_branch_even_if_the_researcher_said_continue(self):
        b = self.one_task(dispositions=["new", "new", "duplicate"])
        self.assertEqual(b["recommendation"], "close")
        self.assertEqual(b["reason"], "diminishing returns: only 2 new facts")

    def test_mostly_duplicates_close_the_branch(self):
        tiers = ("PRIMARY",) * 10
        b = self.one_task(tiers=tiers, dispositions=["new"] * 3 + ["duplicate"] * 7)
        self.assertEqual(b["reason"], "diminishing returns: 7 of 10 findings were duplicates")

    def test_weak_evidence_with_nothing_resolved_closes_the_branch(self):
        tiers = ("INFERRED", "OBSERVED", "INFERRED", "OBSERVED", "INFERRED")
        b = self.one_task(tiers=tiers, raw_kwargs={"unknowns_resolved": []})
        self.assertEqual(b["reason"], "diminishing returns: 5 of 5 findings were inferred or observed")

    def test_weak_evidence_that_resolved_an_unknown_stays_open(self):
        tiers = ("INFERRED", "OBSERVED", "INFERRED", "OBSERVED", "INFERRED")
        self.assertEqual(self.one_task(tiers=tiers)["recommendation"], "open")

    def test_the_depth_cap_closes_a_productive_branch(self):
        b = self.one_task(level=4)
        self.assertEqual((b["recommendation"], b["reason"]), ("close", "depth cap of 4 reached"))

    def test_a_result_with_no_findings_does_not_crash(self):
        b = self.one_task(tiers=())
        self.assertEqual(b["reason"], "diminishing returns: only 0 new facts")

    def test_a_branch_whose_only_task_is_blocked_is_reported_not_closed(self):
        self.start_wave([proposal("p1")])
        tasks.fail_task(self.ws, "p1", "no search")
        tasks.fail_task(self.ws, "p1", "no search")
        b = scoring.score_session(self.ws)["branches"]["wire/framing"]
        self.assertEqual(b["recommendation"], "blocked")

    def test_scoring_waits_for_the_wave_to_finish(self):
        self.start_wave([proposal("p1")])
        with self.assertRaisesRegex(store.RRError, "not finished; still pending: p1"):
            scoring.score_session(self.ws)

    def test_scoring_needs_the_organizers_ledger(self):
        session = self.start_wave([proposal("p1")])
        self.write(f"sessions/{session}/raw/p1.json", raw_result("p1"))
        tasks.complete_task(self.ws, "p1", "done")
        with self.assertRaisesRegex(store.RRError, "run the organizer before scoring"):
            scoring.score_session(self.ws)

    def test_scoring_only_applies_to_deepening(self):
        self.fill_plan()
        tasks.add_session(self.ws, "survey")
        with self.assertRaisesRegex(store.RRError, "only applies to deepening"):
            scoring.score_session(self.ws)

    def test_the_bootstrap_session_scores_as_no_branches(self):
        self.fill_plan()
        self.skip_to("deepening")
        tasks.add_session(self.ws, "deepening")
        self.write("knowledge/tree/README.md", "# Tree\n\n## Known Unknowns\n")
        tasks.complete_task(self.ws, "bootstrap", "built")
        self.assertEqual(scoring.score_session(self.ws)["branches"], {})


class ApplyTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.session = self.start_wave([proposal("dry"), proposal("live", branch="wire/handshake")])
        self.finish(self.session, "dry", raw_result("dry", "irreducible"))
        self.finish(self.session, "live", raw_result("live"))
        self.write(f"sessions/{self.session}/proposals/level_2.json", {"level": 2, "proposals": [
            proposal("d2", branch="wire/framing/sub", level=2, status="proposed"),
            proposal("l2", branch="wire/handshake", level=2, status="proposed"),
        ]})

    def apply(self):
        return scoring.apply_score(self.ws, scoring.score_session(self.ws))

    def test_gate_summary_lists_closed_and_open_branches(self):
        gate = self.apply()
        self.assertEqual(gate["closed"], [{"branch": "wire/framing", "reason": "irreducible"}])
        self.assertEqual(gate["open"], ["wire/handshake"])
        self.assertEqual((gate["proposals_dropped"], gate["proposals_pending"]), (1, 1))
        self.assertEqual(gate["agents_per_batch"], 4)
        branches = store.load_plan(self.ws)["branches"]
        self.assertEqual(branches["wire/framing"]["status"], "closed")
        self.assertEqual(branches["wire/handshake"], {"status": "open", "level": 1})

    def test_proposals_under_a_closed_branch_are_dropped(self):
        self.apply()
        doc = store.read_json(self.ws / "sessions" / self.session / "proposals" / "level_2.json")
        self.assertEqual([p["status"] for p in doc["proposals"]], ["dropped", "proposed"])

    def test_remaining_unknowns_are_recorded_once(self):
        self.apply()
        self.apply()
        text = (self.ws / "knowledge" / "remaining_unknowns.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("## wire/framing"), 1)
        self.assertIn(f"Closed in {self.session}: irreducible", text)
        self.assertIn("- the retry timeout", text)
        self.assertNotIn("wire/handshake", text)

    def test_reopening_restores_the_branch_and_its_proposals(self):
        self.apply()
        result = scoring.reopen_branch(self.ws, "wire/framing")
        self.assertEqual((result["reopened"], result["proposals_restored"], result["note"]),
                         ("wire/framing", 1, ""))
        self.assertEqual(store.load_plan(self.ws)["branches"]["wire/framing"]["status"], "open")
        with self.assertRaisesRegex(store.RRError, "is not closed"):
            scoring.reopen_branch(self.ws, "wire/framing")

    def test_status_reports_branches_and_the_next_step(self):
        self.apply()
        status = report.status(self.ws)
        self.assertEqual(status["branches"]["open"], ["wire/handshake"])
        self.assertEqual(status["branches"]["closed"], [{"branch": "wire/framing", "reason": "irreducible"}])
        self.assertIn("Run the organizer", status["next_step"])


class StatusTests(WorkspaceCase):
    def test_next_step_walks_through_the_gates(self):
        self.assertIn("approve plan", report.status(self.ws)["next_step"])
        self.fill_plan()
        self.assertIn("add-session survey", report.status(self.ws)["next_step"])
        tasks.add_session(self.ws, "survey")
        status = report.status(self.ws)
        self.assertIn("Dispatch the next batch", status["next_step"])
        self.assertEqual(status["session"]["remaining"], 4)
        for tid in ("s01", "s02", "s03"):
            self.write(f"sessions/2026-10-04_survey/raw/{tid}.md", "x")
            tasks.complete_task(self.ws, tid, "x")
        self.write("knowledge/spec.md", "x")
        tasks.complete_task(self.ws, "assemble", "x")
        self.assertIn("set-stage survey done", report.status(self.ws)["next_step"])
        store.set_stage(self.ws, "survey", "done")
        self.assertIn("add-session entity_schema", report.status(self.ws)["next_step"])
        store.set_stage(self.ws, "entity_schema", "done")
        self.assertIn("approve entity_types", report.status(self.ws)["next_step"])

    def test_blocked_tasks_are_surfaced(self):
        self.fill_plan()
        self.skip_to("entity_schema")
        tasks.add_session(self.ws, "entity_schema")
        tasks.fail_task(self.ws, "schema", "boom")
        tasks.fail_task(self.ws, "schema", "boom")
        self.assertIn("Report the blocked tasks", report.status(self.ws)["next_step"])


if __name__ == "__main__":
    unittest.main()
