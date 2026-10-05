"""Shared fixtures: a scaffolded workspace in a temporary folder."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from rrlib import store  # noqa: E402

PLAN_FIELDS = {
    "goal": "Rebuild the protocol from the notes alone",
    "voice": "An engineer writing a reference, not an encyclopedia entry",
    "precision_bar": "Exact field sizes and timeouts",
    "definition_of_done": "A developer can implement a client from the tree",
    "survey_tasks": [
        {"title": "Overview", "description": "What it is and who uses it"},
        {"title": "End to end", "description": "How one exchange flows"},
        {"title": "History", "description": "Versions and context"},
    ],
    "entity_types": ["MessageType", "ErrorCode"],
    "provenance_mapping": {"PRIMARY": ["the RFC"], "EXPERT": [], "SECONDARY": ["vendor docs"]},
}

SCHEMA = {
    "entity_types": [{
        "name": "MessageType",
        "description": "A kind of message",
        "estimated_count": 2,
        "examples": ["HELLO"],
        "properties": [{"name": "code", "type": "number"}, {"name": "reply", "type": "string"}],
    }]
}


def proposal(pid, branch="wire/framing", level=1, status="approved", **overrides):
    p = {
        "id": pid,
        "title": f"Resolve {pid}",
        "description": "Find the missing value",
        "branch": branch,
        "target_file": f"knowledge/tree/{branch}/{pid}.md",
        "unknown_being_resolved": "The maximum frame length in bytes",
        "expected_sources": ["the RFC, section 4"],
        "level": level,
        "status": status,
    }
    p.update(overrides)
    return p


def raw_result(task_id, verdict="continue", tiers=("PRIMARY", "PRIMARY", "PRIMARY"), **overrides):
    doc = {
        "task_id": task_id,
        "verdict": verdict,
        "findings": [{"claim": f"fact {i}", "tier": t, "source": "the RFC"} for i, t in enumerate(tiers)],
        "unknowns_resolved": ["one"],
        "unknowns_opened": [],
        "unknowns_remaining": ["the retry timeout"] if verdict != "exhausted" else [],
        "sources_searched": ["the RFC"],
        "verdict_reason": "below the precision bar" if verdict == "sufficient" else "",
        "proposals": [{"title": "Next", "description": "Find it",
                       "unknown_being_resolved": "The retry timeout in seconds",
                       "expected_sources": ["the RFC"]}] if verdict == "continue" else [],
    }
    doc.update(overrides)
    return doc


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        os.environ["RR_TODAY"] = "2026-10-04"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "research"
        self.ws = Path(store.scaffold(self.root, "Test Subject")["workspace"])

    def fill_plan(self, approve=True, **overrides):
        plan = store.load_plan(self.ws)
        plan.update(json.loads(json.dumps(PLAN_FIELDS)))
        plan.update(overrides)
        store.save_plan(self.ws, plan)
        if approve:
            from rrlib import tasks
            tasks.approve(self.ws, "plan")

    def skip_to(self, stage):
        """Mark every stage before the given one as done."""
        for earlier in store.STAGES[:store.STAGES.index(stage)]:
            store.set_stage(self.ws, earlier, "done")

    def write(self, rel, content):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8", newline="\n")
        else:
            store.write_json(path, content)
        return path

    def start_wave(self, proposals):
        """Run the bootstrap session, then open wave 1 from the given proposals."""
        from rrlib import tasks
        self.fill_plan()
        self.skip_to("deepening")
        boot = tasks.add_session(self.ws, "deepening")["session"]
        self.write("knowledge/tree/README.md", "# Tree\n\n## Known Unknowns\n")
        tasks.complete_task(self.ws, "bootstrap", "built the tree")
        self.write(f"sessions/{boot}/proposals/level_1.json", {"level": 1, "proposals": proposals})
        return tasks.add_session(self.ws, "deepening")["session"]

    def finish(self, session, task_id, raw, dispositions=None):
        """Write a research result, complete its task, and add its ledger entries."""
        from rrlib import tasks
        self.write(f"sessions/{session}/raw/{task_id}.json", raw)
        tasks.complete_task(self.ws, task_id, "done")
        dispositions = dispositions or ["new"] * len(raw["findings"])
        path = self.ws / "sessions" / session / "ledger.json"
        ledger = store.read_json(path) if path.is_file() else {"entries": []}
        ledger["entries"] += [{"task_id": task_id, "finding": i, "disposition": d, "placed_in": "x"}
                              for i, d in enumerate(dispositions)]
        store.write_json(path, ledger)
