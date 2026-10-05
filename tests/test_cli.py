import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import PLAN_FIELDS, REPO


class CliTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "research"

    def rr(self, *args):
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "rr.py"), "--root", str(self.root), *args],
            capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, "RR_TODAY": "2026-10-04"},
        )
        stream = proc.stdout if proc.returncode != 2 else proc.stderr
        return proc.returncode, json.loads(stream)

    def test_survey_flow_from_scaffold_to_assembly(self):
        code, out = self.rr("scaffold", "Wire Protocol")
        self.assertEqual((code, out["slug"]), (0, "wire-protocol"))

        code, out = self.rr("validate", "wire-protocol", "plan")
        self.assertEqual((code, out["ok"]), (1, False))
        code, out = self.rr("approve", "wire-protocol", "plan")
        self.assertEqual(code, 2)
        self.assertIn("cannot approve plan", out["error"])

        plan_path = self.root / "wire-protocol" / "plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan.update(PLAN_FIELDS)
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        self.assertEqual(self.rr("approve", "wire-protocol", "plan"), (0, {"approved": "plan"}))

        code, out = self.rr("add-session", "wire-protocol", "survey")
        self.assertEqual((code, out["task_count"]), (0, 4))
        code, out = self.rr("next-task", "wire-protocol", "--limit", "2")
        self.assertEqual([t["id"] for t in out["tasks"]], ["s01", "s02"])

        code, out = self.rr("complete-task", "wire-protocol", "s01", "wrote it")
        self.assertEqual(code, 2)
        self.assertIn("produced nothing", out["error"])
        code, out = self.rr("fail-task", "wire-protocol", "s01", "agent returned nothing")
        self.assertEqual((code, out["attempts"]), (0, 1))

        raw = self.root / "wire-protocol" / "sessions" / "2026-10-04_survey" / "raw"
        (raw / "s01.md").write_text("# Overview\n", encoding="utf-8")
        code, out = self.rr("complete-task", "wire-protocol", "s01", "wrote it")
        self.assertEqual((code, out["remaining"]), (0, 3))

        self.assertEqual(self.rr("snapshot", "wire-protocol")[0], 0)
        (self.root / "wire-protocol" / "knowledge" / "spec.md").write_text("early", encoding="utf-8")
        code, out = self.rr("check-snapshot", "wire-protocol")
        self.assertEqual((code, out["violations"]), (1, [{"file": "knowledge/spec.md", "change": "added"}]))

        code, out = self.rr("status", "wire-protocol")
        self.assertEqual(out["stages"]["survey"], "in_progress")
        self.assertEqual(out["session"]["remaining"], 3)
        code, out = self.rr("status")
        self.assertEqual([s["slug"] for s in out["subjects"]], ["wire-protocol"])

    def test_unknown_workspace_exits_2_with_a_json_error(self):
        code, out = self.rr("status", "nope")
        self.assertEqual(code, 2)
        self.assertIn("run scaffold first", out["error"])

    def test_non_ascii_subject_round_trips_through_the_console(self):
        code, out = self.rr("scaffold", "東方 Project", "--slug", "touhou")
        self.assertEqual(code, 0)
        code, out = self.rr("status", "touhou")
        self.assertEqual(out["subject"], "東方 Project")

    def test_validate_raw_needs_an_id(self):
        self.rr("scaffold", "Wire Protocol")
        plan_path = self.root / "wire-protocol" / "plan.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan.update(PLAN_FIELDS)
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        self.rr("approve", "wire-protocol", "plan")
        for stage in ("survey", "entity_schema", "entity_enumeration"):
            self.rr("set-stage", "wire-protocol", stage, "done")
        self.assertEqual(self.rr("add-session", "wire-protocol", "deepening")[0], 0)
        code, out = self.rr("validate", "wire-protocol", "raw")
        self.assertEqual(code, 2)
        self.assertIn("needs --id", out["error"])


if __name__ == "__main__":
    unittest.main()
