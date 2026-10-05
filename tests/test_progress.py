import json
import os
import subprocess
import sys
import unittest

from helpers import REPO, WorkspaceCase, proposal, raw_result
from rrlib import progress, report, scoring, tasks


class DispatchMarkTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        self.session = tasks.add_session(self.ws, "survey")["session"]

    def dispatched(self):
        return {t["id"]: t["dispatched"] for t in tasks.load_tasks(self.ws, self.session)["tasks"]}

    def test_handing_out_a_batch_marks_it_as_dispatched(self):
        tasks.next_tasks(self.ws, limit=2, mark=True)
        marks = self.dispatched()
        self.assertTrue(marks["s01"] and marks["s02"])
        self.assertIsNone(marks["s03"])

    def test_looking_at_status_does_not_mark_anything(self):
        report.status(self.ws)
        tasks.next_tasks(self.ws)
        self.assertEqual(set(self.dispatched().values()), {None})

    def test_a_failed_task_is_no_longer_running(self):
        tasks.next_tasks(self.ws, limit=1, mark=True)
        tasks.fail_task(self.ws, "s01", "boom")
        self.assertIsNone(self.dispatched()["s01"])


class SurveyProgressTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        self.session = tasks.add_session(self.ws, "survey")["session"]
        tasks.next_tasks(self.ws, limit=2, mark=True)
        self.write(f"sessions/{self.session}/raw/s01.md", "section\n")
        tasks.complete_task(self.ws, "s01", "wrote it")
        tasks.fail_task(self.ws, "s03", "search timed out")
        tasks.fail_task(self.ws, "s03", "search timed out")

    def test_stage_counts_and_task_states(self):
        data = progress.progress(self.ws)
        self.assertEqual(data["stages"]["survey"], {"status": "in_progress", "done": 1, "total": 4})
        self.assertEqual(data["stages"]["deepening"], {"status": "pending", "done": 0, "total": 0})
        self.assertEqual(data["session"]["name"], self.session)
        self.assertEqual({t["id"]: t["state"] for t in data["session"]["tasks"]},
                         {"s01": "done", "s02": "running", "s03": "blocked", "assemble": "pending"})
        self.assertEqual(data["agent_runs"], 3)
        self.assertEqual(data["waves"], [])

    def test_a_task_that_failed_once_is_waiting_for_its_retry(self):
        tasks.fail_task(self.ws, "s02", "boom")
        states = {t["id"]: t["state"] for t in progress.progress(self.ws)["session"]["tasks"]}
        self.assertEqual(states["s02"], "retry")

    def test_the_text_view_shows_counts_states_and_the_next_step(self):
        text = progress.render(progress.progress(self.ws))
        self.assertIn("Test Subject", text)
        self.assertIn("survey", text)
        self.assertIn("1/4", text)
        self.assertRegex(text, r"running\s+s02")
        self.assertRegex(text, r"blocked\s+s03.*search timed out")
        self.assertIn("Next:", text)
        self.assertIn("Agent runs so far: 3", text)

    def test_a_new_workspace_with_no_session_still_renders(self):
        from rrlib import store
        ws = store.scaffold(self.root, "Fresh")["workspace"]
        text = progress.render(progress.progress(ws))
        self.assertIn("Fresh", text)
        self.assertIn("No session yet", text)


class WaveProgressTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.session = self.start_wave([proposal("dry"), proposal("live", branch="wire/handshake")])
        self.finish(self.session, "dry", raw_result("dry", "irreducible"), ["new", "duplicate", "duplicate"])

    def test_a_wave_in_flight_counts_what_has_come_back_so_far(self):
        wave = progress.progress(self.ws)["waves"][0]
        self.assertEqual((wave["wave"], wave["done"], wave["total"]), ("w01", 1, 2))
        self.assertEqual((wave["findings"], wave["new"], wave["duplicate"]), (3, 1, 2))
        self.assertEqual((wave["unknowns_resolved"], wave["unknowns_opened"]), (1, 0))
        self.assertFalse(wave["scored"])

    def test_findings_are_counted_before_the_organizer_has_written_a_ledger(self):
        (self.ws / "sessions" / self.session / "ledger.json").unlink()
        wave = progress.progress(self.ws)["waves"][0]
        self.assertEqual((wave["findings"], wave["new"], wave["duplicate"]), (3, None, None))

    def test_branches_and_reasons_appear_once_the_wave_is_scored(self):
        self.finish(self.session, "live", raw_result("live"))
        scoring.apply_score(self.ws, scoring.score_session(self.ws))
        data = progress.progress(self.ws)
        self.assertTrue(data["waves"][0]["scored"])
        self.assertEqual(data["branches"], [
            {"branch": "wire/framing", "status": "closed", "level": 1, "reason": "irreducible"},
            {"branch": "wire/handshake", "status": "open", "level": 1, "reason": ""},
        ])
        text = progress.render(data)
        self.assertRegex(text, r"closed\s+wire/framing.*irreducible")
        self.assertRegex(text, r"open\s+wire/handshake")
        self.assertRegex(text, r"w01\s+2/2")

    def test_an_unreadable_result_file_does_not_break_the_view(self):
        (self.ws / "sessions" / self.session / "raw" / "dry.json").write_text("{broken", encoding="utf-8")
        self.assertEqual(progress.progress(self.ws)["waves"][0]["findings"], 0)


class ProgressCliTests(WorkspaceCase):
    def run_rr(self, *args):
        return subprocess.run(
            [sys.executable, str(REPO / "scripts" / "rr.py"), "--root", str(self.root), *args],
            capture_output=True, text=True, encoding="utf-8", env={**os.environ, "RR_TODAY": "2026-10-04"})

    def test_progress_prints_text_and_json_on_request(self):
        proc = self.run_rr("progress", "test-subject")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Test Subject", proc.stdout)
        self.assertIn("Stages", proc.stdout)
        proc = self.run_rr("progress", "test-subject", "--json")
        self.assertEqual(json.loads(proc.stdout)["slug"], "test-subject")

    def test_next_task_from_the_command_line_marks_tasks_as_running(self):
        self.fill_plan()
        tasks.add_session(self.ws, "survey")
        self.run_rr("next-task", "test-subject", "--limit", "1")
        self.assertRegex(self.run_rr("progress", "test-subject").stdout, r"running\s+s01")

    def test_progress_for_an_unknown_subject_exits_2(self):
        proc = self.run_rr("progress", "nope")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("run scaffold first", json.loads(proc.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
