# RecursiveResearch State Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the bookkeeping script that holds all state for a recursive-research project: workspaces, task lists, approvals, validation, branch scoring, and the knowledge guard.

**Architecture:** A small Python package, `scripts/rrlib/`, with one module per responsibility, and one command-line entry point, `scripts/rr.py`, that prints JSON. The skill (plan 2) calls this script and never edits state by hand. Every rule the spec calls absolute (approval before research, stage order, no completion without output, concrete proposals only) is enforced here, so it holds even if an agent ignores its instructions.

**Tech Stack:** Python 3.9 or later, standard library only. Tests use `unittest`.

**Spec:** `docs/specs/2026-10-04-recursive-research-design.md`

This is plan 1 of 2. Plan 2 (`docs/plans/2026-10-05-skill-layer.md`) adds the plugin manifest, agents, skill, and prompt templates, and depends on this one.

## Global Constraints

- Standard library only. No `pip install`, no third-party imports, no ClaudeContainer or Docker.
- Every command prints exactly one JSON object to stdout. Errors the caller can fix print `{"error": "..."}` to stderr.
- Exit codes: `0` ok, `1` validation found errors, `2` the command could not run.
- All files are read and written as UTF-8 with `\n` line endings. Reads accept a byte order mark.
- Paths inside JSON use forward slashes on every platform.
- Provenance tiers, strongest first: `PRIMARY`, `EXPERT`, `SECONDARY`, `INFERRED`, `OBSERVED`, `UNKNOWN`. Only `PRIMARY`, `EXPERT`, and `SECONDARY` take sources in the plan's mapping.
- Stages, in order: `survey`, `entity_schema`, `entity_enumeration`, `deepening`.
- Defaults: depth cap 4, agents per wave 4, `min_new_facts` 3, `max_duplicate_share` 0.6, `max_weak_share` 0.8.
- A task gets one retry: after 2 failed attempts it is blocked.
- Verdicts: `exhausted`, `irreducible`, `sufficient`, `continue`.
- Run all tests from the repository root with `python -m unittest discover -s tests`. On systems where the command is `python3`, use that.

## Decisions this plan makes where the spec was silent

The user should confirm these when reviewing the plan.

1. **Entity rosters go through `raw/`.** The spec says researchers write only to `raw/`, and also that stage 3 researchers produce `knowledge/entities/<type>.json`. Here the researcher writes `raw/<type>.json` and the script validates it and copies it into `knowledge/entities/` (`promote-entity`).
2. **The script closes branches, from the organizer's ledger.** The organizer judges each finding as new, duplicate, or conflict and writes `ledger.json`. The script counts and applies the thresholds. The closing decision is therefore deterministic and repeatable.
3. **Researcher writes to `knowledge/` are detected, not prevented.** Claude Code tool access cannot restrict a path. The script snapshots `knowledge/` before a research batch and reports any change afterwards (`snapshot`, `check-snapshot`).
4. **`continue` requires a proposal.** A research result with verdict `continue` and no proposals is rejected.
5. **Depth is the wave level.** A proposal's `level` is its parent task's level plus 1. A branch that reaches the depth cap closes; proposals past the cap are invalid.

## Review Focus

Inputs the spec implies but does not spell out, most likely first. Each is pinned by a named test.

1. **A JSON file saved with a byte order mark** (common when a Windows editor or PowerShell writes it). It must load. Pinned by `test_read_json_accepts_a_byte_order_mark` in Task 1.
2. **The user edits `plan.json` at a gate and deletes a section** such as `controls.close_thresholds`. Later commands must use defaults, not crash. Pinned by `test_a_hand_edited_plan_missing_sections_loads_with_defaults` in Task 1.
3. **A subject with no Latin letters or digits.** Scaffolding must accept an explicit slug and keep the real subject. Pinned by `test_scaffold_accepts_an_explicit_slug_for_non_latin_subjects` in Task 1 and `test_non_ascii_subject_round_trips_through_the_console` in Task 5.
4. **A researcher who finds nothing** returns zero findings. Scoring must not divide by zero. Pinned by `test_a_result_with_no_findings_does_not_crash` in Task 4.
5. **A session interrupted between scoring and the gate**, so `score --apply` runs twice. Closed branches must not be recorded twice. Pinned by `test_remaining_unknowns_are_recorded_once` in Task 4.

## File Structure

| File | Responsibility |
|---|---|
| `scripts/rrlib/__init__.py` | Empty; marks the package |
| `scripts/rrlib/store.py` | Workspace layout, atomic JSON read and write, the default plan, slugs |
| `scripts/rrlib/provenance.py` | The fixed tiers and finding their tags in Markdown |
| `scripts/rrlib/validate.py` | Checks on every file an agent or user writes |
| `scripts/rrlib/tasks.py` | Sessions, approvals, handing out and completing tasks, promoting entity rosters |
| `scripts/rrlib/scoring.py` | Scoring branches, closing them, reopening them |
| `scripts/rrlib/report.py` | Status and the next step |
| `scripts/rrlib/guard.py` | Snapshot of `knowledge/` and the check against it |
| `scripts/rr.py` | The command line |
| `tests/helpers.py` | Shared fixtures |
| `tests/test_*.py` | One test file per module |

Dependencies run one way: `store` and `provenance` import nothing from the package; `validate` imports both; `tasks` imports `store` and `validate`; `scoring`, `report`, and `guard` import `tasks`; `rr.py` imports all of them.

---

### Task 1: Workspace store

**Files:**
- Create: `.gitignore`
- Create: `scripts/rrlib/__init__.py` (empty)
- Create: `scripts/rrlib/store.py`
- Create: `tests/helpers.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `store.RRError(Exception)`
  - `store.STAGES: tuple[str, ...]`, `store.STAGE_STATUSES: tuple[str, ...]`
  - `store.today() -> str` (ISO date; the `RR_TODAY` environment variable overrides it for tests)
  - `store.slugify(text: str) -> str`
  - `store.type_id(name: str) -> str`
  - `store.is_under(branch: str, parent: str) -> bool`
  - `store.read_json(path) -> Any`, `store.write_json(path, data) -> None`
  - `store.default_plan(subject: str, slug: str) -> dict`
  - `store.scaffold(root, subject: str, slug: str | None = None) -> dict` with keys `workspace`, `slug`, `plan`
  - `store.workspace(root, slug: str) -> Path`
  - `store.list_workspaces(root) -> list[str]`
  - `store.load_plan(ws) -> dict`, `store.save_plan(ws, plan: dict) -> None`
  - `store.set_stage(ws, stage: str, status: str) -> dict`
  - `helpers.WorkspaceCase` with `self.root`, `self.ws`, `fill_plan(approve=True, **overrides)`, `skip_to(stage)`, `write(rel, content)`, `start_wave(proposals)`, `finish(session, task_id, raw, dispositions=None)`
  - `helpers.PLAN_FIELDS`, `helpers.SCHEMA`, `helpers.proposal(...)`, `helpers.raw_result(...)`, `helpers.REPO`

`tests/helpers.py` is written in full here. Its `fill_plan`, `start_wave`, and `finish` methods import `rrlib.tasks` inside the method body, so they only work from Task 3 onward. Task 1's tests do not call them with approval.

- [ ] **Step 1: Create the package marker and ignore file**

Create an empty file `scripts/rrlib/__init__.py`.

Create `.gitignore`:

```
__pycache__/
*.pyc
*.tmp
```

- [ ] **Step 2: Write the shared fixtures**

Create `tests/helpers.py`:

```python
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
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_store.py`:

```python
import unittest

from helpers import WorkspaceCase
from rrlib import store


class SlugTests(unittest.TestCase):
    def test_slug_is_lowercase_and_hyphenated(self):
        self.assertEqual(store.slugify("The Magic of Scheherazade (NES)"), "the-magic-of-scheherazade-nes")

    def test_slug_with_no_usable_characters_is_an_error(self):
        with self.assertRaises(store.RRError):
            store.slugify("東方")

    def test_slug_is_capped_at_60_characters(self):
        self.assertLessEqual(len(store.slugify("word " * 40)), 60)

    def test_type_id_splits_pascal_case(self):
        self.assertEqual(store.type_id("CharacterClass"), "character_class")
        self.assertEqual(store.type_id("HTTP header"), "http_header")

    def test_is_under_matches_whole_path_segments_only(self):
        self.assertTrue(store.is_under("wire/framing", "wire"))
        self.assertTrue(store.is_under("wire", "wire"))
        self.assertFalse(store.is_under("wireless", "wire"))


class ScaffoldTests(WorkspaceCase):
    def test_scaffold_creates_layout_and_default_plan(self):
        for sub in ("knowledge/entities", "knowledge/tree", "sessions"):
            self.assertTrue((self.ws / sub).is_dir(), sub)
        plan = store.load_plan(self.ws)
        self.assertEqual(plan["subject"], "Test Subject")
        self.assertEqual(plan["slug"], "test-subject")
        self.assertEqual(plan["controls"]["depth_cap"], 4)
        self.assertEqual(plan["controls"]["max_agents_per_wave"], 4)
        self.assertEqual(plan["controls"]["close_thresholds"],
                         {"min_new_facts": 3, "max_duplicate_share": 0.6, "max_weak_share": 0.8})
        self.assertEqual(plan["approvals"], {"plan": False, "entity_types": False})
        self.assertEqual(set(plan["stages"].values()), {"pending"})

    def test_scaffold_refuses_to_overwrite_an_existing_workspace(self):
        with self.assertRaises(store.RRError):
            store.scaffold(self.root, "Test Subject")

    def test_scaffold_accepts_an_explicit_slug_for_non_latin_subjects(self):
        result = store.scaffold(self.root, "東方", slug="touhou")
        self.assertEqual(result["slug"], "touhou")
        self.assertEqual(store.load_plan(self.root / "touhou")["subject"], "東方")

    def test_workspace_lookup_fails_clearly_when_missing(self):
        with self.assertRaisesRegex(store.RRError, "run scaffold first"):
            store.workspace(self.root, "nope")

    def test_list_workspaces(self):
        store.scaffold(self.root, "Another")
        self.assertEqual(store.list_workspaces(self.root), ["another", "test-subject"])
        self.assertEqual(store.list_workspaces(self.root / "missing"), [])


class JsonTests(WorkspaceCase):
    def test_read_json_accepts_a_byte_order_mark(self):
        path = self.ws / "bom.json"
        path.write_bytes(b"\xef\xbb\xbf" + b'{"a": 1}')
        self.assertEqual(store.read_json(path), {"a": 1})

    def test_read_json_reports_invalid_json_as_rrerror(self):
        path = self.write("bad.json", "{not json")
        with self.assertRaisesRegex(store.RRError, "not valid JSON"):
            store.read_json(path)

    def test_read_json_reports_a_missing_file_as_rrerror(self):
        with self.assertRaisesRegex(store.RRError, "missing file"):
            store.read_json(self.ws / "absent.json")

    def test_write_json_leaves_no_temporary_files(self):
        store.write_json(self.ws / "x.json", {"名前": "値"})
        self.assertEqual(store.read_json(self.ws / "x.json"), {"名前": "値"})
        self.assertEqual(list(self.ws.glob("*.tmp")), [])

    def test_a_hand_edited_plan_missing_sections_loads_with_defaults(self):
        plan = store.load_plan(self.ws)
        del plan["controls"]["close_thresholds"]
        del plan["controls"]["max_agents_per_wave"]
        del plan["branches"]
        plan["goal"] = "kept"
        store.save_plan(self.ws, plan)
        loaded = store.load_plan(self.ws)
        self.assertEqual(loaded["controls"]["max_agents_per_wave"], 4)
        self.assertEqual(loaded["controls"]["close_thresholds"]["min_new_facts"], 3)
        self.assertEqual(loaded["controls"]["depth_cap"], 4)
        self.assertEqual(loaded["branches"], {})
        self.assertEqual(loaded["goal"], "kept")

    def test_a_plan_that_is_not_an_object_is_an_rrerror(self):
        store.write_json(self.ws / "plan.json", ["oops"])
        with self.assertRaisesRegex(store.RRError, "must be a JSON object"):
            store.load_plan(self.ws)

    def test_set_stage_rejects_unknown_values(self):
        store.set_stage(self.ws, "survey", "done")
        self.assertEqual(store.load_plan(self.ws)["stages"]["survey"], "done")
        with self.assertRaises(store.RRError):
            store.set_stage(self.ws, "survey", "finished")
        with self.assertRaises(store.RRError):
            store.set_stage(self.ws, "nonsense", "done")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `python -m unittest discover -s tests -p "test_store.py"`
Expected: FAIL with `ImportError: cannot import name 'store' from 'rrlib'`

- [ ] **Step 5: Write the implementation**

Create `scripts/rrlib/store.py`:

```python
"""Workspace layout and JSON state for one research subject."""
import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path

STAGES = ("survey", "entity_schema", "entity_enumeration", "deepening")
STAGE_STATUSES = ("pending", "in_progress", "done")


class RRError(Exception):
    """A problem the caller can fix. The CLI prints it and exits with code 2."""


def today():
    return os.environ.get("RR_TODAY") or date.today().isoformat()


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-")
    if not slug:
        raise RRError(f"cannot build a folder name from {text!r}; pass --slug using letters or digits")
    return slug


def type_id(name):
    """File-safe id for an entity type: 'CharacterClass' -> 'character_class'."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(name))
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    if not s:
        raise RRError(f"cannot build a file name from entity type {name!r}")
    return s


def is_under(branch, parent):
    """True if branch is parent or one of its descendants."""
    return branch == parent or branch.startswith(parent + "/")


def read_json(path):
    try:
        # utf-8-sig also accepts files saved with a byte order mark (common on Windows)
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        raise RRError(f"missing file: {Path(path).as_posix()}") from None
    except json.JSONDecodeError as e:
        raise RRError(f"{Path(path).as_posix()} is not valid JSON: {e}") from None


def write_json(path, data):
    """Write atomically, so an interrupted run never leaves a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def default_plan(subject, slug):
    return {
        "schema_version": 1,
        "subject": subject,
        "slug": slug,
        "created": today(),
        "goal": "",
        "voice": "",
        "precision_bar": "",
        "definition_of_done": "",
        "survey_tasks": [],
        "entity_types": [],
        "provenance_mapping": {"PRIMARY": [], "EXPERT": [], "SECONDARY": []},
        "controls": {
            "depth_cap": 4,
            "max_agents_per_wave": 4,
            "close_thresholds": {
                "min_new_facts": 3,
                "max_duplicate_share": 0.6,
                "max_weak_share": 0.8,
            },
        },
        "approvals": {"plan": False, "entity_types": False},
        "stages": {stage: "pending" for stage in STAGES},
        "sessions": [],
        "branches": {},
    }


def scaffold(root, subject, slug=None):
    if not str(subject).strip():
        raise RRError("subject is empty")
    slug = slugify(slug or subject)
    ws = Path(root) / slug
    if ws.exists():
        raise RRError(f"{ws.as_posix()} already exists; resume it or pass a different --slug")
    for sub in ("knowledge/entities", "knowledge/tree", "sessions"):
        (ws / sub).mkdir(parents=True)
    write_json(ws / "plan.json", default_plan(subject.strip(), slug))
    return {"workspace": ws.as_posix(), "slug": slug, "plan": (ws / "plan.json").as_posix()}


def workspace(root, slug):
    ws = Path(root) / slug
    if not (ws / "plan.json").is_file():
        raise RRError(f"no research workspace at {ws.as_posix()}; run scaffold first")
    return ws


def list_workspaces(root):
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "plan.json").is_file())


def load_plan(ws):
    """Read plan.json, restoring any section a hand edit removed."""
    plan = read_json(Path(ws) / "plan.json")
    if not isinstance(plan, dict):
        raise RRError(f"{(Path(ws) / 'plan.json').as_posix()} must be a JSON object")
    defaults = default_plan(plan.get("subject", ""), plan.get("slug", Path(ws).name))
    for key, value in defaults.items():
        plan.setdefault(key, value)
    for key in ("controls", "approvals", "stages"):
        if not isinstance(plan[key], dict):
            plan[key] = defaults[key]
        for inner, value in defaults[key].items():
            plan[key].setdefault(inner, value)
    thresholds = plan["controls"]["close_thresholds"]
    if not isinstance(thresholds, dict):
        thresholds = plan["controls"]["close_thresholds"] = {}
    for inner, value in defaults["controls"]["close_thresholds"].items():
        thresholds.setdefault(inner, value)
    return plan


def save_plan(ws, plan):
    write_json(Path(ws) / "plan.json", plan)


def set_stage(ws, stage, status):
    if stage not in STAGES:
        raise RRError(f"unknown stage {stage!r}; expected one of {', '.join(STAGES)}")
    if status not in STAGE_STATUSES:
        raise RRError(f"unknown status {status!r}; expected one of {', '.join(STAGE_STATUSES)}")
    plan = load_plan(ws)
    plan["stages"][stage] = status
    save_plan(ws, plan)
    return {"stage": stage, "status": status}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_store.py"`
Expected: `Ran 17 tests` and `OK`

- [ ] **Step 7: Commit**

```bash
git add .gitignore scripts/rrlib/__init__.py scripts/rrlib/store.py tests/helpers.py tests/test_store.py
git commit -m "Add the workspace store"
```

---

### Task 2: Provenance and validation

**Files:**
- Create: `scripts/rrlib/provenance.py`
- Create: `scripts/rrlib/validate.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `store.RRError`, `store.is_under`, `store.read_json`, `store.type_id`.
- Produces:
  - `provenance.TIERS`, `provenance.WEAK`, `provenance.MAPPED_TIERS` (tuples of str)
  - `provenance.stronger(a: str, b: str) -> str`
  - `provenance.scan_markdown(text: str) -> {"counts": dict[str, int], "unknown_tags": list[str]}`
  - An issue is `{"level": "error" | "warning", "where": str, "message": str}`.
  - `validate.issue(level, where, message) -> dict`, `validate.has_errors(issues) -> bool`
  - `validate.VERDICTS`, `validate.PROPOSAL_STATUSES`, `validate.ID_RE`
  - `validate.validate_plan(plan: dict) -> list[issue]`
  - `validate.validate_entity_schema(doc) -> list[issue]`
  - `validate.find_type(schema_doc: dict, tid: str) -> dict` (raises `RRError` if absent)
  - `validate.validate_entity_file(doc, schema_type: dict) -> list[issue]`
  - `validate.validate_raw(doc, task_id: str | None = None) -> list[issue]`
  - `validate.validate_proposals(doc, plan: dict) -> list[issue]`
  - `validate.validate_tree(tree_dir) -> list[issue]`

File shapes these validators define (plan 2's prompts must match them):

- `knowledge/entities.json`: `{"entity_types": [{"name", "description", "estimated_count", "examples", "properties": [{"name", "type", ...}]}], "relationships": [...]}`
- An entity roster: `{"entity_type", "count", "entities": [{"name", "properties": {...}, "provenance": "<tier>" | {"<property>": "<tier>"}, "notes"}]}`
- A stage 4 research result: `{"task_id", "branch", "verdict", "verdict_reason", "findings": [{"claim", "tier", "source"}], "unknowns_resolved", "unknowns_opened", "unknowns_remaining", "sources_searched", "proposals"}`
- A proposals file: `{"level", "proposals": [{"id", "title", "description", "branch", "target_file", "unknown_being_resolved", "expected_sources", "level", "status"}]}`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validate.py`:

```python
import copy
import unittest

from helpers import PLAN_FIELDS, SCHEMA, WorkspaceCase, proposal, raw_result
from rrlib import provenance, store, validate


def errors(issues):
    return [i["message"] for i in issues if i["level"] == "error"]


class ProvenanceTests(unittest.TestCase):
    def test_scan_counts_tier_tags_including_unknown_with_a_range(self):
        scan = provenance.scan_markdown("HP is 4 [PRIMARY]. Speed [UNKNOWN: est 3-5]. Also [PRIMARY].")
        self.assertEqual(scan["counts"]["PRIMARY"], 2)
        self.assertEqual(scan["counts"]["UNKNOWN"], 1)

    def test_scan_reports_legacy_tags_and_ignores_links_and_checkboxes(self):
        scan = provenance.scan_markdown("- [ ] todo\n- [x] done\nSee [API](http://x). Old [ROM_VERIFIED].")
        self.assertEqual(scan["unknown_tags"], ["ROM_VERIFIED"])
        self.assertEqual(sum(scan["counts"].values()), 0)

    def test_stronger_follows_the_fixed_precedence(self):
        self.assertEqual(provenance.stronger("SECONDARY", "PRIMARY"), "PRIMARY")
        self.assertEqual(provenance.stronger("EXPERT", "INFERRED"), "EXPERT")
        self.assertEqual(provenance.stronger("UNKNOWN", "OBSERVED"), "OBSERVED")


class PlanTests(WorkspaceCase):
    def plan(self, **overrides):
        plan = store.load_plan(self.ws)
        plan.update(copy.deepcopy(PLAN_FIELDS))
        plan.update(overrides)
        return plan

    def test_a_complete_plan_has_no_issues(self):
        self.assertEqual(validate.validate_plan(self.plan()), [])

    def test_a_fresh_scaffold_is_not_a_valid_plan(self):
        self.assertTrue(validate.has_errors(validate.validate_plan(store.load_plan(self.ws))))

    def test_plan_needs_a_goal_tasks_entity_types_and_a_mapped_source(self):
        issues = validate.validate_plan(self.plan(
            goal=" ", survey_tasks=[], entity_types=[],
            provenance_mapping={"PRIMARY": [], "EXPERT": [], "SECONDARY": []}))
        self.assertEqual({i["where"] for i in issues},
                         {"goal", "survey_tasks", "entity_types", "provenance_mapping"})

    def test_plan_rejects_sources_mapped_to_a_tier_that_takes_none(self):
        issues = validate.validate_plan(self.plan(provenance_mapping={"PRIMARY": ["x"], "INFERRED": ["y"]}))
        self.assertEqual([i["where"] for i in issues], ["provenance_mapping.INFERRED"])

    def test_plan_rejects_bad_controls(self):
        plan = self.plan()
        plan["controls"] = {"depth_cap": 0, "max_agents_per_wave": "4",
                            "close_thresholds": {"min_new_facts": -1, "max_duplicate_share": 1.5,
                                                 "max_weak_share": True}}
        self.assertEqual(len(errors(validate.validate_plan(plan))), 5)


class EntityTests(unittest.TestCase):
    def roster(self, **entity):
        base = {"name": "HELLO", "properties": {"code": 1, "reply": "WELCOME"}, "provenance": "PRIMARY"}
        base.update(entity)
        return {"entity_type": "MessageType", "count": 1, "entities": [base]}

    def test_schema_is_valid(self):
        self.assertEqual(validate.validate_entity_schema(SCHEMA), [])

    def test_schema_rejects_types_that_would_share_a_file_name(self):
        doc = {"entity_types": [dict(SCHEMA["entity_types"][0]),
                                dict(SCHEMA["entity_types"][0], name="message_type")]}
        self.assertIn("message_type.json", errors(validate.validate_entity_schema(doc))[0])

    def test_schema_rejects_an_empty_list_and_types_without_properties(self):
        self.assertTrue(errors(validate.validate_entity_schema({"entity_types": []})))
        doc = {"entity_types": [{"name": "Thing", "description": "x", "properties": []}]}
        self.assertTrue(errors(validate.validate_entity_schema(doc)))

    def test_roster_with_one_tier_for_the_whole_entity_is_valid(self):
        self.assertEqual(validate.validate_entity_file(self.roster(), SCHEMA["entity_types"][0]), [])

    def test_roster_flags_values_without_a_tier(self):
        issues = validate.validate_entity_file(self.roster(provenance={"code": "PRIMARY"}),
                                               SCHEMA["entity_types"][0])
        self.assertEqual(errors(issues), ["property reply has no provenance tier"])

    def test_roster_requires_unknown_for_null_values(self):
        doc = self.roster(properties={"code": 1, "reply": None})
        self.assertIn("must be UNKNOWN", errors(validate.validate_entity_file(doc, SCHEMA["entity_types"][0]))[0])
        doc = self.roster(properties={"code": 1, "reply": None},
                          provenance={"code": "PRIMARY", "reply": "UNKNOWN"})
        self.assertEqual(validate.validate_entity_file(doc, SCHEMA["entity_types"][0]), [])

    def test_roster_flags_missing_extra_and_duplicate(self):
        doc = self.roster(properties={"code": 1, "colour": "red"})
        doc["entities"].append(copy.deepcopy(doc["entities"][0]))
        messages = errors(validate.validate_entity_file(doc, SCHEMA["entity_types"][0]))
        self.assertIn("says 1 but there are 2 entities", messages[0])
        self.assertIn("missing property reply (use null if unknown)", messages)
        self.assertIn("property colour is not in the schema", messages)
        self.assertIn("appears more than once", messages)

    def test_an_empty_roster_is_an_error(self):
        doc = {"entity_type": "MessageType", "count": 0, "entities": []}
        self.assertTrue(errors(validate.validate_entity_file(doc, SCHEMA["entity_types"][0])))

    def test_find_type_by_id(self):
        self.assertEqual(validate.find_type(SCHEMA, "message_type")["name"], "MessageType")
        with self.assertRaises(store.RRError):
            validate.find_type(SCHEMA, "ship")


class RawTests(unittest.TestCase):
    def test_a_continue_result_is_valid(self):
        self.assertEqual(validate.validate_raw(raw_result("p1"), "p1"), [])

    def test_result_must_belong_to_the_task(self):
        self.assertTrue(errors(validate.validate_raw(raw_result("p1"), "p2")))

    def test_each_verdict_needs_its_evidence(self):
        self.assertTrue(errors(validate.validate_raw(raw_result("p1", "exhausted", unknowns_remaining=["x"]))))
        self.assertTrue(errors(validate.validate_raw(raw_result("p1", "irreducible", sources_searched=[]))))
        self.assertTrue(errors(validate.validate_raw(raw_result("p1", "sufficient", verdict_reason=""))))
        self.assertTrue(errors(validate.validate_raw(raw_result("p1", "continue", proposals=[]))))
        self.assertTrue(errors(validate.validate_raw(raw_result("p1", "done"))))
        for verdict in ("exhausted", "irreducible", "sufficient"):
            self.assertEqual(validate.validate_raw(raw_result("p1", verdict)), [], verdict)

    def test_findings_need_a_claim_a_real_tier_and_a_source(self):
        doc = raw_result("p1")
        doc["findings"] = [{"claim": "", "tier": "PRIMARY", "source": "x"},
                           {"claim": "a", "tier": "UNKNOWN", "source": "x"},
                           {"claim": "b", "tier": "PRIMARY", "source": " "}]
        self.assertEqual(len(errors(validate.validate_raw(doc))), 3)

    def test_a_result_that_is_not_an_object_is_an_error(self):
        self.assertTrue(errors(validate.validate_raw(["nope"])))


class ProposalTests(WorkspaceCase):
    def check(self, *proposals, **branches):
        plan = store.load_plan(self.ws)
        plan["branches"] = branches
        return errors(validate.validate_proposals({"proposals": list(proposals)}, plan))

    def test_a_concrete_proposal_is_valid(self):
        self.assertEqual(self.check(proposal("p1")), [])

    def test_vague_unknowns_are_rejected(self):
        for text in ("Research this topic further", "More detail about framing", "tbd"):
            self.assertTrue(self.check(proposal("p1", unknown_being_resolved=text)), text)

    def test_proposal_needs_sources_and_a_target_inside_its_branch(self):
        self.assertTrue(self.check(proposal("p1", expected_sources=[])))
        self.assertTrue(self.check(proposal("p1", target_file="knowledge/tree/other/p1.md")))
        self.assertTrue(self.check(proposal("p1", target_file="knowledge/spec.md")))
        self.assertTrue(self.check(proposal("p1", branch="../escape")))

    def test_level_past_the_depth_cap_is_rejected(self):
        self.assertEqual(self.check(proposal("p1", level=4)), [])
        self.assertIn("past the depth cap of 4", self.check(proposal("p1", level=5))[0])

    def test_proposals_on_a_closed_branch_or_its_children_are_rejected(self):
        closed = {"wire": {"status": "closed", "reason": "exhausted"}}
        self.assertIn("is closed", self.check(proposal("p1"), **closed)[0])
        self.assertEqual(self.check(proposal("p1", branch="wireless/x"), **closed), [])

    def test_duplicate_ids_and_bad_status_are_rejected(self):
        self.assertIn("duplicate id", self.check(proposal("p1"), proposal("p1")))
        self.assertTrue(self.check(proposal("p1", status="maybe")))

    def test_skipped_proposals_are_not_checked_further(self):
        self.assertEqual(self.check(proposal("p1", status="skipped", unknown_being_resolved="")), [])


class TreeTests(WorkspaceCase):
    def test_missing_tree_is_an_error(self):
        self.assertTrue(errors(validate.validate_tree(self.ws / "knowledge" / "absent")))

    def test_every_folder_needs_a_readme_with_known_unknowns(self):
        self.write("knowledge/tree/README.md", "# Tree [PRIMARY]\n\n## Known Unknowns\n")
        self.write("knowledge/tree/wire/README.md", "# Wire [PRIMARY]\n")
        (self.ws / "knowledge/tree/empty").mkdir()
        issues = validate.validate_tree(self.ws / "knowledge" / "tree")
        self.assertEqual(sorted(i["where"] for i in issues), ["empty", "wire/README.md"])

    def test_leaves_need_provenance(self):
        self.write("knowledge/tree/README.md", "# Tree\n\n## Known Unknowns\n")
        self.write("knowledge/tree/frame_sizes.json", {"_meta": {"provenance": "PRIMARY"}, "max": 9})
        self.write("knowledge/tree/handshake.md", "The client speaks first.\n")
        self.write("knowledge/tree/timeouts.json", {"_meta": {"provenance": "PRIMARY", "source": "RFC"}})
        self.write("knowledge/tree/retry.md", "Three retries [SECONDARY]. Legacy [GUIDE_SOURCED].\n")
        issues = validate.validate_tree(self.ws / "knowledge" / "tree")
        self.assertEqual({(i["level"], i["where"]) for i in issues}, {
            ("warning", "README.md"),
            ("error", "frame_sizes.json"),
            ("error", "handshake.md"),
            ("warning", "retry.md"),
        })

    def test_generic_file_names_get_a_warning(self):
        self.write("knowledge/tree/README.md", "# Tree [PRIMARY]\n\n## Known Unknowns\n")
        self.write("knowledge/tree/data.json", {"_meta": {"provenance": "UNKNOWN"}})
        issues = validate.validate_tree(self.ws / "knowledge" / "tree")
        self.assertEqual([(i["level"], i["where"]) for i in issues], [("warning", "data.json")])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest discover -s tests -p "test_validate.py"`
Expected: FAIL with `ImportError: cannot import name 'provenance' from 'rrlib'`

- [ ] **Step 3: Write the provenance module**

Create `scripts/rrlib/provenance.py`:

```python
"""The fixed provenance tiers and how to find their tags in Markdown."""
import re

# Strongest first. UNKNOWN is a valid tag but never wins a conflict.
TIERS = ("PRIMARY", "EXPERT", "SECONDARY", "INFERRED", "OBSERVED", "UNKNOWN")
WEAK = ("INFERRED", "OBSERVED")
MAPPED_TIERS = ("PRIMARY", "EXPERT", "SECONDARY")

# [PRIMARY] or [UNKNOWN: est 3-5]; the lookahead skips Markdown links like [API](url)
TAG_RE = re.compile(r"\[([A-Z][A-Z_]+)(?::[^\]\n]*)?\](?!\()")


def stronger(a, b):
    """Return whichever of two tiers wins a conflict."""
    return a if TIERS.index(a) <= TIERS.index(b) else b


def scan_markdown(text):
    counts = {tier: 0 for tier in TIERS}
    unknown_tags = []
    for match in TAG_RE.finditer(text):
        tag = match.group(1)
        if tag in counts:
            counts[tag] += 1
        elif tag not in unknown_tags:
            unknown_tags.append(tag)
    return {"counts": counts, "unknown_tags": unknown_tags}
```

- [ ] **Step 4: Write the validation module**

Create `scripts/rrlib/validate.py`:

```python
"""Checks on every file an agent or the user writes. Each returns a list of issues."""
import re
from pathlib import Path

from .provenance import MAPPED_TIERS, TIERS, scan_markdown
from .store import RRError, is_under, read_json, type_id

VERDICTS = ("exhausted", "irreducible", "sufficient", "continue")
PROPOSAL_STATUSES = ("proposed", "approved", "skipped", "dropped")
GENERIC_NAMES = ("data.json", "notes.md")
ID_RE = re.compile(r"[A-Za-z0-9_-]+")
# Wording that asks for "more" without naming what is missing
VAGUE_RE = re.compile(
    r"\b(further|deeper|more (detail|details|information|research|about)|in (more|greater) (detail|depth))\b",
    re.IGNORECASE,
)


def issue(level, where, message):
    return {"level": level, "where": where, "message": message}


def has_errors(issues):
    return any(i["level"] == "error" for i in issues)


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def validate_plan(plan):
    issues = []
    for key in ("subject", "goal", "voice", "precision_bar", "definition_of_done"):
        if not _text(plan.get(key)):
            issues.append(issue("error", key, "must not be empty"))

    survey = plan.get("survey_tasks")
    if not isinstance(survey, list) or len(survey) < 3:
        issues.append(issue("error", "survey_tasks", "needs at least 3 tasks"))
    else:
        for i, task in enumerate(survey):
            if not isinstance(task, dict) or not _text(task.get("title")) or not _text(task.get("description")):
                issues.append(issue("error", f"survey_tasks[{i}]", "needs a title and a description"))

    types = plan.get("entity_types")
    if not isinstance(types, list) or not types or not all(_text(t) for t in types):
        issues.append(issue("error", "entity_types", "name at least one expected entity type"))

    mapping = plan.get("provenance_mapping")
    if not isinstance(mapping, dict):
        issues.append(issue("error", "provenance_mapping", "must be an object"))
    else:
        for tier in mapping:
            if tier not in MAPPED_TIERS:
                issues.append(issue("error", f"provenance_mapping.{tier}",
                                    f"only {', '.join(MAPPED_TIERS)} take sources"))
        if not any(mapping.get(tier) for tier in MAPPED_TIERS):
            issues.append(issue("error", "provenance_mapping", "map at least one concrete source to a tier"))

    controls = plan.get("controls") if isinstance(plan.get("controls"), dict) else {}
    for key in ("depth_cap", "max_agents_per_wave"):
        value = controls.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            issues.append(issue("error", f"controls.{key}", "must be a whole number of 1 or more"))
    thresholds = controls.get("close_thresholds") if isinstance(controls.get("close_thresholds"), dict) else {}
    floor = thresholds.get("min_new_facts")
    if not isinstance(floor, int) or isinstance(floor, bool) or floor < 0:
        issues.append(issue("error", "controls.close_thresholds.min_new_facts", "must be a whole number of 0 or more"))
    for key in ("max_duplicate_share", "max_weak_share"):
        value = thresholds.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
            issues.append(issue("error", f"controls.close_thresholds.{key}", "must be a number from 0 to 1"))
    return issues


def validate_entity_schema(doc):
    types = doc.get("entity_types") if isinstance(doc, dict) else None
    if not isinstance(types, list) or not types:
        return [issue("error", "entity_types", "must be a non-empty list")]
    issues, seen = [], set()
    for i, et in enumerate(types):
        where = f"entity_types[{i}]"
        if not isinstance(et, dict) or not _text(et.get("name")):
            issues.append(issue("error", where, "needs a name"))
            continue
        where = et["name"]
        try:
            tid = type_id(et["name"])
        except RRError as e:
            issues.append(issue("error", where, str(e)))
            continue
        if tid in seen:
            issues.append(issue("error", where, f"another type already uses the file name {tid}.json"))
        seen.add(tid)
        props = et.get("properties")
        if not isinstance(props, list) or not props:
            issues.append(issue("error", where, "needs at least one property"))
        elif not all(isinstance(p, dict) and _text(p.get("name")) for p in props):
            issues.append(issue("error", where, "every property needs a name"))
        if not _text(et.get("description")):
            issues.append(issue("warning", where, "has no description"))
    return issues


def find_type(schema_doc, tid):
    for et in schema_doc.get("entity_types", []):
        if isinstance(et, dict) and _text(et.get("name")) and type_id(et["name"]) == tid:
            return et
    raise RRError(f"entities.json has no entity type with id {tid!r}")


def validate_entity_file(doc, schema_type):
    if not isinstance(doc, dict) or not isinstance(doc.get("entities"), list):
        return [issue("error", "entities", "must be a list")]
    issues, seen = [], set()
    expected = [p["name"] for p in schema_type["properties"]]
    entities = doc["entities"]
    if not entities:
        issues.append(issue("error", "entities", "is empty; record a failed task instead of an empty roster"))
    if doc.get("count") != len(entities):
        issues.append(issue("error", "count", f"says {doc.get('count')} but there are {len(entities)} entities"))
    for i, entity in enumerate(entities):
        if not isinstance(entity, dict) or not _text(entity.get("name")):
            issues.append(issue("error", f"entities[{i}]", "needs a name"))
            continue
        where = entity["name"]
        if where in seen:
            issues.append(issue("error", where, "appears more than once"))
        seen.add(where)
        props = entity.get("properties")
        if not isinstance(props, dict):
            issues.append(issue("error", where, "needs a properties object"))
            continue
        for name in expected:
            if name not in props:
                issues.append(issue("error", where, f"missing property {name} (use null if unknown)"))
        for name in props:
            if name not in expected:
                issues.append(issue("error", where, f"property {name} is not in the schema"))
        prov = entity.get("provenance")
        for name in props:
            tier = prov if isinstance(prov, str) else prov.get(name) if isinstance(prov, dict) else None
            if tier not in TIERS:
                issues.append(issue("error", where, f"property {name} has no provenance tier"))
            elif props[name] is None and tier != "UNKNOWN":
                issues.append(issue("error", where, f"property {name} is null, so its tier must be UNKNOWN"))
    return issues


def validate_raw(doc, task_id=None):
    """A stage 4 research result: sessions/<session>/raw/<task>.json."""
    if not isinstance(doc, dict):
        return [issue("error", "file", "must be a JSON object")]
    issues = []
    if task_id is not None and doc.get("task_id") != task_id:
        issues.append(issue("error", "task_id", f"is {doc.get('task_id')!r} but this is the result for {task_id!r}"))
    verdict = doc.get("verdict")
    if verdict not in VERDICTS:
        issues.append(issue("error", "verdict", f"must be one of {', '.join(VERDICTS)}"))
    findings = doc.get("findings")
    if not isinstance(findings, list):
        issues.append(issue("error", "findings", "must be a list (it may be empty)"))
        findings = []
    for i, finding in enumerate(findings):
        where = f"findings[{i}]"
        if not isinstance(finding, dict) or not _text(finding.get("claim")):
            issues.append(issue("error", where, "needs a claim"))
            continue
        if finding.get("tier") not in TIERS or finding.get("tier") == "UNKNOWN":
            issues.append(issue("error", where, "needs a tier; list unknowns under unknowns_remaining instead"))
        if not _text(finding.get("source")):
            issues.append(issue("error", where, "needs a source"))
    for key in ("unknowns_resolved", "unknowns_opened", "unknowns_remaining", "sources_searched", "proposals"):
        if not isinstance(doc.get(key, []), list):
            issues.append(issue("error", key, "must be a list"))
    if verdict == "exhausted" and doc.get("unknowns_remaining"):
        issues.append(issue("error", "verdict", "exhausted is not allowed while unknowns_remaining is non-empty"))
    if verdict == "irreducible" and not doc.get("sources_searched"):
        issues.append(issue("error", "verdict", "irreducible requires the list of sources_searched"))
    if verdict == "sufficient" and not _text(doc.get("verdict_reason")):
        issues.append(issue("error", "verdict", "sufficient requires a verdict_reason"))
    if verdict == "continue" and not doc.get("proposals"):
        issues.append(issue("error", "verdict", "continue requires at least one proposal naming a concrete unknown"))
    return issues


def validate_proposals(doc, plan):
    props = doc.get("proposals") if isinstance(doc, dict) else None
    if not isinstance(props, list):
        return [issue("error", "proposals", "must be a list")]
    issues, seen = [], set()
    cap = plan["controls"]["depth_cap"]
    closed = [name for name, b in plan.get("branches", {}).items() if b.get("status") == "closed"]
    for i, p in enumerate(props):
        if not isinstance(p, dict):
            issues.append(issue("error", f"proposals[{i}]", "must be an object"))
            continue
        pid = _text(p.get("id"))
        where = pid or f"proposals[{i}]"
        if not ID_RE.fullmatch(pid):
            issues.append(issue("error", where, "id must use only letters, digits, '_' or '-'"))
        elif pid in seen:
            issues.append(issue("error", where, "duplicate id"))
        seen.add(pid)
        if p.get("status") not in PROPOSAL_STATUSES:
            issues.append(issue("error", where, f"status must be one of {', '.join(PROPOSAL_STATUSES)}"))
        if p.get("status") in ("skipped", "dropped"):
            continue
        for key in ("title", "description"):
            if not _text(p.get(key)):
                issues.append(issue("error", where, f"{key} must not be empty"))
        unknown = _text(p.get("unknown_being_resolved"))
        if len(unknown) < 15 or VAGUE_RE.search(unknown):
            issues.append(issue("error", where,
                                "unknown_being_resolved must name one concrete missing fact, not ask for more research"))
        sources = p.get("expected_sources")
        if not isinstance(sources, list) or not sources or not all(_text(s) for s in sources):
            issues.append(issue("error", where, "expected_sources must list where to look"))
        branch = _text(p.get("branch"))
        target = _text(p.get("target_file"))
        if not branch or branch.startswith("/") or ".." in branch.split("/"):
            issues.append(issue("error", where, "branch must be a folder path inside knowledge/tree"))
        elif not target.startswith(f"knowledge/tree/{branch}/") or ".." in target.split("/"):
            issues.append(issue("error", where, f"target_file must be inside knowledge/tree/{branch}/"))
        elif any(is_under(branch, c) for c in closed):
            issues.append(issue("error", where, f"branch {branch} is closed; reopen it before proposing work on it"))
        level = p.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or level < 1:
            issues.append(issue("error", where, "level must be a whole number of 1 or more"))
        elif level > cap:
            issues.append(issue("error", where, f"level {level} is past the depth cap of {cap}"))
    return issues


def validate_tree(tree_dir):
    tree = Path(tree_dir)
    if not tree.is_dir():
        return [issue("error", tree.as_posix(), "the knowledge tree does not exist")]
    issues = []
    for folder in [tree, *sorted(p for p in tree.rglob("*") if p.is_dir())]:
        rel = folder.relative_to(tree).as_posix()
        readme = folder / "README.md"
        if not readme.is_file():
            issues.append(issue("error", rel, "folder has no README.md"))
        elif "## Known Unknowns" not in readme.read_text(encoding="utf-8-sig"):
            issues.append(issue("error", f"{rel}/README.md", "has no '## Known Unknowns' section"))
    for path in sorted(p for p in tree.rglob("*") if p.is_file()):
        rel = path.relative_to(tree).as_posix()
        if path.name in GENERIC_NAMES:
            issues.append(issue("warning", rel, "generic file name; name it after what it holds"))
        if path.suffix == ".json":
            try:
                doc = read_json(path)
            except RRError as e:
                issues.append(issue("error", rel, str(e)))
                continue
            meta = doc.get("_meta") if isinstance(doc, dict) else None
            if not isinstance(meta, dict) or meta.get("provenance") not in TIERS:
                issues.append(issue("error", rel, f"needs _meta.provenance set to one of {', '.join(TIERS)}"))
            elif meta["provenance"] != "UNKNOWN" and not _text(meta.get("source")):
                issues.append(issue("error", rel, "needs _meta.source"))
        elif path.suffix == ".md":
            scan = scan_markdown(path.read_text(encoding="utf-8-sig"))
            if not sum(scan["counts"].values()):
                level = "warning" if path.name == "README.md" else "error"
                issues.append(issue(level, rel, "contains no provenance tags"))
            for tag in scan["unknown_tags"]:
                issues.append(issue("warning", rel, f"[{tag}] is not a provenance tier"))
    return issues
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_validate.py"`
Expected: `Ran 33 tests` and `OK`

- [ ] **Step 6: Commit**

```bash
git add scripts/rrlib/provenance.py scripts/rrlib/validate.py tests/test_validate.py
git commit -m "Add provenance tiers and file validation"
```

---

### Task 3: Sessions and tasks

**Files:**
- Create: `scripts/rrlib/tasks.py`
- Test: `tests/test_tasks.py`

**Interfaces:**
- Consumes: everything Task 1 and Task 2 produce.
- Produces:
  - `tasks.MAX_ATTEMPTS = 2`
  - `tasks.session_dir(ws, session: str) -> Path`
  - `tasks.current_session(ws) -> str` (raises `RRError` if there is none)
  - `tasks.load_tasks(ws, session: str) -> dict` with keys `session`, `stage`, `tasks`
  - `tasks.approve(ws, what: "plan" | "entity_types") -> dict`
  - `tasks.default_tasks(ws, stage: str) -> list[dict]`
  - `tasks.add_session(ws, stage: str, tasks: list[dict] | None = None) -> dict` with keys `session`, `stage`, `task_count`
  - `tasks.next_tasks(ws, limit: int | None = None, session: str | None = None) -> dict` with keys `session`, `stage`, `tasks`, `remaining`, `blocked`, `complete`
  - `tasks.complete_task(ws, task_id: str, summary: str, session=None) -> dict` with keys `completed`, `verdict`, `remaining`
  - `tasks.fail_task(ws, task_id: str, reason: str, session=None) -> dict` with keys `failed`, `attempts`, `blocked`
  - `tasks.promote_entity(ws, tid: str, session=None) -> dict` with keys `promoted`, `issues`, and `file` when promoted

A task record has these keys: `id`, `title`, `description`, `branch`, `level`, `target`, `unknown`, `expected_sources`, `solo`, `output`, `passes`, `attempts`, `last_error`, `verdict`.

Session names are `<date>_<stage>`, or `<date>_deepening_w<NN>` for deepening, where `w00` is the bootstrap.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tasks.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest discover -s tests -p "test_tasks.py"`
Expected: FAIL with `ImportError: cannot import name 'tasks' from 'rrlib'`

- [ ] **Step 3: Write the implementation**

Create `scripts/rrlib/tasks.py`:

```python
"""Sessions and their task lists: create, hand out, complete, fail."""
import shutil
from pathlib import Path

from .store import RRError, STAGES, load_plan, read_json, save_plan, today, type_id, write_json
from .validate import (ID_RE, find_type, has_errors, validate_entity_file, validate_entity_schema,
                       validate_plan, validate_proposals, validate_raw)

MAX_ATTEMPTS = 2  # one try plus one retry; after that the task is reported as blocked

SCHEMA_TASK = {
    "id": "schema",
    "title": "Identify entity types and their schemas",
    "description": "Read knowledge/spec.md and write knowledge/entities.json: every entity type, "
                   "its properties, a rough count, relationships, and two or three examples.",
    "solo": True,
    "output": "knowledge/entities.json",
}
BOOTSTRAP_TASK = {
    "id": "bootstrap",
    "title": "Build the knowledge tree and the first proposals",
    "description": "Build knowledge/tree/ from the spec and entity files, with a README ending in "
                   "Known Unknowns in every folder, then write level 1 proposals from those unknowns.",
    "solo": True,
    "output": "knowledge/tree/README.md",
}
ASSEMBLE_TASK = {
    "id": "assemble",
    "title": "Assemble and review the survey",
    "description": "Merge the raw sections into knowledge/spec.md in task order, add a table of "
                   "contents and cross-references, and fix inconsistencies.",
    "solo": True,
    "output": "knowledge/spec.md",
}


def session_dir(ws, session):
    return Path(ws) / "sessions" / session


def current_session(ws):
    sessions = load_plan(ws)["sessions"]
    if not sessions:
        raise RRError("there is no session yet; run add-session first")
    return sessions[-1]


def load_tasks(ws, session):
    return read_json(session_dir(ws, session) / "tasks.json")


def _errors(issues):
    return "; ".join(f"{i['where']}: {i['message']}" for i in issues if i["level"] == "error")


def approve(ws, what):
    """Record a user approval. Refuses while the thing being approved is invalid."""
    plan = load_plan(ws)
    if what == "plan":
        issues = validate_plan(plan)
    elif what == "entity_types":
        issues = validate_entity_schema(read_json(Path(ws) / "knowledge" / "entities.json"))
    else:
        raise RRError(f"cannot approve {what!r}; expected plan or entity_types")
    if has_errors(issues):
        raise RRError(f"cannot approve {what}: {_errors(issues)}")
    plan["approvals"][what] = True
    save_plan(ws, plan)
    return {"approved": what}


def default_tasks(ws, stage):
    """The task list a stage starts with, built from what earlier stages left on disk."""
    plan = load_plan(ws)
    if stage == "survey":
        tasks = [{"id": f"s{i:02d}", "title": t["title"], "description": t["description"]}
                 for i, t in enumerate(plan["survey_tasks"], 1)]
        return tasks + [dict(ASSEMBLE_TASK)]
    if stage == "entity_schema":
        return [dict(SCHEMA_TASK)]
    if stage == "entity_enumeration":
        schema = read_json(Path(ws) / "knowledge" / "entities.json")
        return [{"id": type_id(et["name"]), "title": f"Enumerate every {et['name']}",
                 "description": et.get("description", ""), "output": "sessions/{session}/raw/{id}.json"}
                for et in schema["entity_types"]]
    if stage == "deepening":
        if not any("_deepening_w" in s for s in plan["sessions"]):
            return [dict(BOOTSTRAP_TASK)]
        tasks = []
        for path in sorted((session_dir(ws, plan["sessions"][-1]) / "proposals").glob("*.json")):
            doc = read_json(path)
            issues = validate_proposals(doc, plan)
            if has_errors(issues):
                raise RRError(f"{path.name} has invalid proposals: {_errors(issues)}")
            for p in doc["proposals"]:
                if p["status"] == "approved":
                    tasks.append({"id": p["id"], "title": p["title"], "description": p["description"],
                                  "branch": p["branch"], "level": p["level"], "target": p["target_file"],
                                  "unknown": p["unknown_being_resolved"],
                                  "expected_sources": p["expected_sources"],
                                  "output": "sessions/{session}/raw/{id}.json"})
        if not tasks:
            raise RRError("no approved proposals; mark proposals as approved or finish with consolidation")
        return tasks
    raise RRError(f"unknown stage {stage!r}; expected one of {', '.join(STAGES)}")


def add_session(ws, stage, tasks=None):
    if stage not in STAGES:
        raise RRError(f"unknown stage {stage!r}; expected one of {', '.join(STAGES)}")
    plan = load_plan(ws)
    if not plan["approvals"]["plan"]:
        raise RRError("the plan is not approved yet; no research may start")
    for earlier in STAGES[:STAGES.index(stage)]:
        if plan["stages"][earlier] != "done":
            raise RRError(f"the {earlier} stage is not done yet; stages run in order")
    if stage == "entity_enumeration" and not plan["approvals"]["entity_types"]:
        raise RRError("the entity type list is not approved yet")
    if tasks is None:
        tasks = default_tasks(ws, stage)
    if not tasks:
        raise RRError("a session needs at least one task")

    if stage == "deepening":
        wave = sum(1 for s in plan["sessions"] if "_deepening_w" in s)
        name = f"{today()}_deepening_w{wave:02d}"
    else:
        name = f"{today()}_{stage}"
    sdir = session_dir(ws, name)
    if sdir.exists():
        raise RRError(f"session {name} already exists")

    filled, seen = [], set()
    for t in tasks:
        tid = str(t.get("id", "")).strip()
        if not ID_RE.fullmatch(tid):
            raise RRError(f"task id {tid!r} must use only letters, digits, '_' or '-'")
        if tid in seen:
            raise RRError(f"duplicate task id {tid}")
        seen.add(tid)
        if not str(t.get("title", "")).strip():
            raise RRError(f"task {tid} has no title")
        output = t.get("output", "sessions/{session}/raw/{id}.md")
        filled.append({
            "id": tid,
            "title": t["title"],
            "description": t.get("description", ""),
            "branch": t.get("branch", ""),
            "level": int(t.get("level", 0)),
            "target": t.get("target", ""),
            "unknown": t.get("unknown", ""),
            "expected_sources": t.get("expected_sources", []),
            "solo": bool(t.get("solo", False)),
            "output": output.replace("{session}", name).replace("{id}", tid),
            "passes": False,
            "attempts": 0,
            "last_error": None,
            "verdict": None,
        })

    (sdir / "raw").mkdir(parents=True)
    (sdir / "proposals").mkdir()
    write_json(sdir / "tasks.json", {"session": name, "stage": stage, "tasks": filled})
    (sdir / "activity.md").write_text(f"# Activity log -- {plan['subject']} -- {stage}\n\n",
                                      encoding="utf-8", newline="\n")
    plan["sessions"].append(name)
    plan["stages"][stage] = "in_progress"
    save_plan(ws, plan)
    return {"session": name, "stage": stage, "task_count": len(filled)}


def _blocked(task):
    return not task["passes"] and task["attempts"] >= MAX_ATTEMPTS


def next_tasks(ws, limit=None, session=None):
    """The next batch to dispatch. A solo task is only ever returned on its own."""
    session = session or current_session(ws)
    doc = load_tasks(ws, session)
    if limit is None:
        limit = load_plan(ws)["controls"]["max_agents_per_wave"]
    if limit < 1:
        raise RRError("limit must be 1 or more")
    batch = []
    for task in doc["tasks"]:
        if task["passes"] or _blocked(task):
            continue
        if task["solo"]:
            if not batch:
                batch = [task]
            break
        batch.append(task)
        if len(batch) >= limit:
            break
    remaining = sum(1 for t in doc["tasks"] if not t["passes"])
    return {
        "session": session,
        "stage": doc["stage"],
        "tasks": batch,
        "remaining": remaining,
        "blocked": [{"id": t["id"], "last_error": t["last_error"]} for t in doc["tasks"] if _blocked(t)],
        "complete": remaining == 0,
    }


def _find(doc, task_id):
    for task in doc["tasks"]:
        if task["id"] == task_id:
            return task
    raise RRError(f"session {doc['session']} has no task {task_id!r}")


def _log(ws, session, line):
    with open(session_dir(ws, session) / "activity.md", "a", encoding="utf-8", newline="\n") as f:
        f.write(f"- {today()} {line}\n")


def complete_task(ws, task_id, summary, session=None):
    """Mark a task done. Refuses unless the task's output file exists and is valid."""
    session = session or current_session(ws)
    doc = load_tasks(ws, session)
    task = _find(doc, task_id)
    if task["passes"]:
        raise RRError(f"task {task_id} is already complete")
    output = Path(ws) / task["output"]
    if not output.is_file() or output.stat().st_size == 0:
        raise RRError(f"task {task_id} produced nothing at {task['output']}; use fail-task to record why")
    if doc["stage"] == "deepening" and "/raw/" in task["output"]:
        raw = read_json(output)
        issues = validate_raw(raw, task_id)
        if has_errors(issues):
            raise RRError(f"{task['output']} is not a valid result: {_errors(issues)}")
        task["verdict"] = raw["verdict"]
    task["passes"] = True
    task["last_error"] = None
    write_json(session_dir(ws, session) / "tasks.json", doc)
    _log(ws, session, f"{task_id}: {summary}")
    return {"completed": task_id, "verdict": task["verdict"],
            "remaining": sum(1 for t in doc["tasks"] if not t["passes"])}


def fail_task(ws, task_id, reason, session=None):
    session = session or current_session(ws)
    doc = load_tasks(ws, session)
    task = _find(doc, task_id)
    if task["passes"]:
        raise RRError(f"task {task_id} is already complete")
    task["attempts"] += 1
    task["last_error"] = reason
    write_json(session_dir(ws, session) / "tasks.json", doc)
    _log(ws, session, f"{task_id}: FAILED (attempt {task['attempts']}): {reason}")
    return {"failed": task_id, "attempts": task["attempts"], "blocked": _blocked(task)}


def promote_entity(ws, tid, session=None):
    """Validate a researcher's roster in raw/ and copy it into knowledge/entities/."""
    session = session or current_session(ws)
    source = session_dir(ws, session) / "raw" / f"{tid}.json"
    schema_type = find_type(read_json(Path(ws) / "knowledge" / "entities.json"), tid)
    issues = validate_entity_file(read_json(source), schema_type)
    if has_errors(issues):
        return {"promoted": False, "issues": issues}
    target = Path(ws) / "knowledge" / "entities" / f"{tid}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return {"promoted": True, "file": f"knowledge/entities/{tid}.json", "issues": issues}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_tasks.py"`
Expected: `Ran 19 tests` and `OK`

- [ ] **Step 5: Run the whole suite**

Run: `python -m unittest discover -s tests`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add scripts/rrlib/tasks.py tests/test_tasks.py
git commit -m "Add sessions, approvals and task tracking"
```

---

### Task 4: Branch scoring and status

**Files:**
- Create: `scripts/rrlib/scoring.py`
- Create: `scripts/rrlib/report.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `store`, `provenance.WEAK`, `tasks.MAX_ATTEMPTS`, `tasks.current_session`, `tasks.load_tasks`, `tasks.session_dir`, `tasks.next_tasks`.
- Produces:
  - `scoring.DISPOSITIONS = ("new", "duplicate", "conflict")`
  - `scoring.score_session(ws, session=None) -> {"session": str, "branches": {name: {...}}}`. Each branch has `tasks`, `completed`, `blocked`, `level`, `findings`, `new`, `duplicate`, `conflict`, `weak`, `unknowns_resolved`, `unknowns_opened`, `remaining`, `verdicts`, `recommendation` (`close`, `open`, or `blocked`), and `reason`.
  - `scoring.apply_score(ws, result: dict) -> dict` with keys `session`, `closed` (list of `{"branch", "reason"}`), `open`, `blocked`, `proposals_dropped`, `proposals_pending`, `agents_per_batch`
  - `scoring.reopen_branch(ws, branch: str) -> dict` with keys `reopened`, `proposals_restored`, `note`
  - `report.status(ws) -> dict` with keys `subject`, `slug`, `approvals`, `stages`, `controls`, `session`, `branches`, `next_step`

The organizer's ledger, which scoring reads, is `sessions/<session>/ledger.json`: `{"entries": [{"task_id", "finding", "disposition", "placed_in"}]}`, with one entry per finding of every completed task.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scoring.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest discover -s tests -p "test_scoring.py"`
Expected: FAIL with `ImportError: cannot import name 'report' from 'rrlib'`

- [ ] **Step 3: Write the scoring module**

Create `scripts/rrlib/scoring.py`:

```python
"""Decide which branches of the knowledge tree have run dry, and close them."""
from pathlib import Path

from .provenance import WEAK
from .store import RRError, is_under, load_plan, read_json, save_plan, write_json
from .tasks import MAX_ATTEMPTS, current_session, load_tasks, session_dir

DISPOSITIONS = ("new", "duplicate", "conflict")
# When no researcher on a branch said "continue", report the most informative reason
VERDICT_PRIORITY = ("irreducible", "sufficient", "exhausted")


def _recommend(b, thresholds, depth_cap):
    if not b["completed"]:
        return "blocked", "no task on this branch completed"
    if "continue" not in b["verdicts"]:
        return "close", next(v for v in VERDICT_PRIORITY if v in b["verdicts"])
    if b["new"] < thresholds["min_new_facts"]:
        return "close", f"diminishing returns: only {b['new']} new facts"
    if b["findings"] and b["duplicate"] / b["findings"] > thresholds["max_duplicate_share"]:
        return "close", f"diminishing returns: {b['duplicate']} of {b['findings']} findings were duplicates"
    if b["findings"] and b["unknowns_resolved"] == 0 and b["weak"] / b["findings"] > thresholds["max_weak_share"]:
        return "close", f"diminishing returns: {b['weak']} of {b['findings']} findings were inferred or observed"
    if b["level"] >= depth_cap:
        return "close", f"depth cap of {depth_cap} reached"
    return "open", ""


def score_session(ws, session=None):
    """Count what each branch gained in a finished wave and recommend close or open."""
    plan = load_plan(ws)
    session = session or current_session(ws)
    doc = load_tasks(ws, session)
    if doc["stage"] != "deepening":
        raise RRError("score only applies to deepening sessions")
    pending = [t["id"] for t in doc["tasks"] if not t["passes"] and t["attempts"] < MAX_ATTEMPTS]
    if pending:
        raise RRError(f"the wave is not finished; still pending: {', '.join(pending)}")

    dispositions = {}
    ledger = session_dir(ws, session) / "ledger.json"
    if ledger.is_file():
        for entry in read_json(ledger).get("entries", []):
            dispositions[(entry.get("task_id"), entry.get("finding"))] = entry.get("disposition")

    branches = {}
    for task in doc["tasks"]:
        if not task["branch"]:
            continue  # the bootstrap task belongs to no branch
        b = branches.setdefault(task["branch"], {
            "tasks": 0, "completed": 0, "blocked": 0, "level": 0, "findings": 0,
            "new": 0, "duplicate": 0, "conflict": 0, "weak": 0,
            "unknowns_resolved": 0, "unknowns_opened": 0, "remaining": [], "verdicts": [],
        })
        b["tasks"] += 1
        b["level"] = max(b["level"], task["level"])
        if not task["passes"]:
            b["blocked"] += 1
            continue
        b["completed"] += 1
        b["verdicts"].append(task["verdict"])
        raw = read_json(Path(ws) / task["output"])
        for i, finding in enumerate(raw["findings"]):
            disposition = dispositions.get((task["id"], i))
            if disposition not in DISPOSITIONS:
                raise RRError(f"ledger.json has no valid entry for task {task['id']} finding {i}; "
                              "run the organizer before scoring")
            b["findings"] += 1
            b[disposition] += 1
            if finding["tier"] in WEAK:
                b["weak"] += 1
        b["unknowns_resolved"] += len(raw.get("unknowns_resolved", []))
        b["unknowns_opened"] += len(raw.get("unknowns_opened", []))
        for unknown in raw.get("unknowns_remaining", []):
            if unknown not in b["remaining"]:
                b["remaining"].append(unknown)

    thresholds = plan["controls"]["close_thresholds"]
    for b in branches.values():
        b["recommendation"], b["reason"] = _recommend(b, thresholds, plan["controls"]["depth_cap"])
    return {"session": session, "branches": branches}


def _proposal_files(ws, session):
    return sorted((session_dir(ws, session) / "proposals").glob("*.json"))


def apply_score(ws, result):
    """Close the branches recommended for closing and build the gate summary."""
    plan = load_plan(ws)
    session = result["session"]
    closed, still_open, blocked, newly_closed = [], [], [], []
    for name, b in sorted(result["branches"].items()):
        previous = plan["branches"].get(name, {})
        if b["recommendation"] == "close":
            if previous.get("status") != "closed":
                newly_closed.append(name)
            plan["branches"][name] = {"status": "closed", "reason": b["reason"],
                                      "session": session, "level": b["level"]}
            closed.append({"branch": name, "reason": b["reason"]})
        else:
            plan["branches"][name] = {"status": "open", "level": b["level"]}
            (blocked if b["recommendation"] == "blocked" else still_open).append(name)
    save_plan(ws, plan)

    all_closed = [name for name, b in plan["branches"].items() if b["status"] == "closed"]
    dropped = pending = 0
    for path in _proposal_files(ws, session):
        doc = read_json(path)
        changed = False
        for p in doc.get("proposals", []):
            if p.get("status") not in ("proposed", "approved"):
                continue
            if any(is_under(p.get("branch", ""), c) for c in all_closed):
                p["status"] = "dropped"
                p["dropped_reason"] = "branch closed"
                dropped += 1
                changed = True
            else:
                pending += 1
        if changed:
            write_json(path, doc)

    if newly_closed:
        path = Path(ws) / "knowledge" / "remaining_unknowns.md"
        text = "" if path.is_file() else "# Remaining unknowns\n"
        for name in newly_closed:
            b = result["branches"][name]
            text += f"\n## {name}\n\nClosed in {session}: {b['reason']}\n\n"
            text += "".join(f"- {u}\n" for u in b["remaining"]) or "- none recorded\n"
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(text)

    return {"session": session, "closed": closed, "open": still_open, "blocked": blocked,
            "proposals_dropped": dropped, "proposals_pending": pending,
            "agents_per_batch": plan["controls"]["max_agents_per_wave"]}


def reopen_branch(ws, branch):
    plan = load_plan(ws)
    record = plan["branches"].get(branch)
    if not record or record.get("status") != "closed":
        raise RRError(f"branch {branch!r} is not closed")
    plan["branches"][branch] = {"status": "open", "level": record.get("level", 0), "reopened": True}
    save_plan(ws, plan)
    restored = 0
    for path in _proposal_files(ws, current_session(ws)):
        doc = read_json(path)
        changed = False
        for p in doc.get("proposals", []):
            if p.get("status") == "dropped" and is_under(p.get("branch", ""), branch):
                p["status"] = "proposed"
                p.pop("dropped_reason", None)
                restored += 1
                changed = True
        if changed:
            write_json(path, doc)
    cap = plan["controls"]["depth_cap"]
    note = ""
    if record.get("level", 0) >= cap:
        note = f"this branch is at the depth cap of {cap}; raise controls.depth_cap in plan.json to go deeper"
    return {"reopened": branch, "proposals_restored": restored, "note": note}
```

- [ ] **Step 4: Write the report module**

Create `scripts/rrlib/report.py`:

```python
"""Where a research project stands and what to do next."""
from .store import STAGES, load_plan
from .tasks import next_tasks


def _next_step(plan, session):
    if not plan["approvals"]["plan"]:
        return "Complete plan.json, show it to the user, and record their approval (approve plan)."
    if session and session["runnable"]:
        return f"Dispatch the next batch of tasks in {session['name']} (next-task)."
    stages = plan["stages"]
    for stage in STAGES:
        if stages[stage] != "in_progress":
            continue
        if session and session["blocked"]:
            return f"Report the blocked tasks in {session['name']} to the user."
        if stage == "deepening":
            return (f"Run the organizer for {session['name']}, then score --apply and present the gate; "
                    "when no proposals remain, consolidate and set-stage deepening done.")
        return f"Finish the {stage} stage, then set-stage {stage} done."
    for stage in STAGES:
        if stages[stage] == "pending":
            if stage == "entity_enumeration" and not plan["approvals"]["entity_types"]:
                return "Show the entity type list to the user and record their approval (approve entity_types)."
            return f"Start the {stage} stage (add-session {stage})."
    return "All four stages are done."


def status(ws):
    plan = load_plan(ws)
    session = None
    if plan["sessions"]:
        batch = next_tasks(ws, limit=1)
        session = {"name": batch["session"], "stage": batch["stage"], "remaining": batch["remaining"],
                   "blocked": batch["blocked"], "runnable": bool(batch["tasks"])}
    branches = plan["branches"]
    return {
        "subject": plan["subject"],
        "slug": plan["slug"],
        "approvals": plan["approvals"],
        "stages": plan["stages"],
        "controls": plan["controls"],
        "session": session,
        "branches": {
            "open": sorted(n for n, b in branches.items() if b["status"] == "open"),
            "closed": [{"branch": n, "reason": b["reason"]}
                       for n, b in sorted(branches.items()) if b["status"] == "closed"],
        },
        "next_step": _next_step(plan, session),
    }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_scoring.py"`
Expected: `Ran 20 tests` and `OK`

- [ ] **Step 6: Commit**

```bash
git add scripts/rrlib/scoring.py scripts/rrlib/report.py tests/test_scoring.py
git commit -m "Add branch scoring, closing and status"
```

---

### Task 5: Knowledge guard and command line

**Files:**
- Create: `scripts/rrlib/guard.py`
- Create: `scripts/rr.py`
- Test: `tests/test_guard.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: every module above.
- Produces:
  - `guard.snapshot(ws) -> {"session": str, "files": int}`
  - `guard.check_snapshot(ws) -> {"session": str, "clean": bool, "violations": [{"file", "change"}]}` where `change` is `added`, `removed`, or `modified`
  - `rr.build_parser() -> argparse.ArgumentParser`
  - `rr.main(argv=None) -> int`
  - The commands plan 2's skill calls, all taking `--root <folder>` (default `research`) before the command:

| Command | Arguments |
|---|---|
| `scaffold` | `<subject> [--slug <slug>]` |
| `approve` | `<slug> plan\|entity_types` |
| `add-session` | `<slug> <stage>` |
| `next-task` | `<slug> [--limit N]` |
| `complete-task` | `<slug> <task_id> <summary>` |
| `fail-task` | `<slug> <task_id> <reason>` |
| `set-stage` | `<slug> <stage> pending\|in_progress\|done` |
| `validate` | `<slug> plan\|entity_schema\|entity\|proposals\|raw\|tree [--id <id>]` |
| `promote-entity` | `<slug> <type_id>` |
| `snapshot` | `<slug>` |
| `check-snapshot` | `<slug>` |
| `score` | `<slug> [--apply]` |
| `reopen-branch` | `<slug> <branch>` |
| `status` | `[<slug>]` |

- [ ] **Step 1: Write the failing guard tests**

Create `tests/test_guard.py`:

```python
import unittest

from helpers import WorkspaceCase
from rrlib import guard, store, tasks


class GuardTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.fill_plan()
        self.session = tasks.add_session(self.ws, "survey")["session"]
        self.write("knowledge/spec.md", "original\n")

    def test_writing_only_to_raw_is_clean(self):
        self.assertEqual(guard.snapshot(self.ws), {"session": self.session, "files": 1})
        self.write(f"sessions/{self.session}/raw/s01.md", "section\n")
        self.assertEqual(guard.check_snapshot(self.ws),
                         {"session": self.session, "clean": True, "violations": []})

    def test_added_modified_and_removed_knowledge_files_are_violations(self):
        self.write("knowledge/tree/README.md", "tree\n")
        guard.snapshot(self.ws)
        self.write("knowledge/spec.md", "rewritten by a researcher\n")
        self.write("knowledge/tree/sneaky.md", "new\n")
        (self.ws / "knowledge/tree/README.md").unlink()
        result = guard.check_snapshot(self.ws)
        self.assertFalse(result["clean"])
        self.assertEqual(result["violations"], [
            {"file": "knowledge/spec.md", "change": "modified"},
            {"file": "knowledge/tree/README.md", "change": "removed"},
            {"file": "knowledge/tree/sneaky.md", "change": "added"},
        ])

    def test_checking_without_a_snapshot_is_an_error(self):
        with self.assertRaisesRegex(store.RRError, "missing file"):
            guard.check_snapshot(self.ws)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Write the failing command-line tests**

Create `tests/test_cli.py`:

```python
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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m unittest discover -s tests -p "test_guard.py"`
Expected: FAIL with `ImportError: cannot import name 'guard' from 'rrlib'`

Run: `python -m unittest discover -s tests -p "test_cli.py"`
Expected: FAIL; every test errors with `json.decoder.JSONDecodeError` because `scripts/rr.py` does not exist yet.

- [ ] **Step 4: Write the guard module**

Create `scripts/rrlib/guard.py`:

```python
"""Detect writes to knowledge/ during a research batch, when only raw/ may change."""
import hashlib
from pathlib import Path

from .store import read_json, write_json
from .tasks import current_session, session_dir

SNAPSHOT = "knowledge_snapshot.json"


def _hashes(ws):
    knowledge = Path(ws) / "knowledge"
    return {p.relative_to(ws).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(knowledge.rglob("*")) if p.is_file()}


def snapshot(ws):
    """Record the state of knowledge/ before researchers are dispatched."""
    session = current_session(ws)
    hashes = _hashes(ws)
    write_json(session_dir(ws, session) / SNAPSHOT, hashes)
    return {"session": session, "files": len(hashes)}


def check_snapshot(ws):
    """Compare knowledge/ with the last snapshot. Any difference is a violation."""
    session = current_session(ws)
    before = read_json(session_dir(ws, session) / SNAPSHOT)
    after = _hashes(ws)
    violations = sorted(
        [{"file": f, "change": "added"} for f in after if f not in before]
        + [{"file": f, "change": "removed"} for f in before if f not in after]
        + [{"file": f, "change": "modified"} for f in after if f in before and after[f] != before[f]],
        key=lambda v: v["file"],
    )
    return {"session": session, "clean": not violations, "violations": violations}
```

- [ ] **Step 5: Write the command line**

Create `scripts/rr.py`:

```python
#!/usr/bin/env python3
"""Bookkeeping for recursive-research. Every command prints one JSON object.

Exit codes: 0 = ok, 1 = validation found errors, 2 = the command could not run.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rrlib import guard, report, scoring, store, tasks, validate  # noqa: E402

VALIDATE_TARGETS = ("plan", "entity_schema", "entity", "proposals", "raw", "tree")


def run_validate(ws, args):
    plan = store.load_plan(ws)
    knowledge = ws / "knowledge"
    if args.what == "plan":
        return validate.validate_plan(plan)
    if args.what == "entity_schema":
        return validate.validate_entity_schema(store.read_json(knowledge / "entities.json"))
    if args.what == "tree":
        return validate.validate_tree(knowledge / "tree")
    session = tasks.session_dir(ws, tasks.current_session(ws))
    if args.what == "proposals":
        issues = []
        for path in sorted((session / "proposals").glob("*.json")):
            issues += validate.validate_proposals(store.read_json(path), plan)
        return issues
    if not args.id:
        raise store.RRError(f"validate {args.what} needs --id")
    if args.what == "entity":
        schema_type = validate.find_type(store.read_json(knowledge / "entities.json"), args.id)
        return validate.validate_entity_file(store.read_json(session / "raw" / f"{args.id}.json"), schema_type)
    return validate.validate_raw(store.read_json(session / "raw" / f"{args.id}.json"), args.id)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default="research", help="folder that holds research workspaces")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scaffold", help="create the workspace for a new subject")
    p.add_argument("subject")
    p.add_argument("--slug")

    p = sub.add_parser("approve", help="record a user approval")
    p.add_argument("slug")
    p.add_argument("what", choices=("plan", "entity_types"))

    p = sub.add_parser("add-session", help="start a stage, or the next deepening wave")
    p.add_argument("slug")
    p.add_argument("stage", choices=store.STAGES)

    p = sub.add_parser("next-task", help="the next batch of tasks to dispatch")
    p.add_argument("slug")
    p.add_argument("--limit", type=int)

    p = sub.add_parser("complete-task", help="mark a task done")
    p.add_argument("slug")
    p.add_argument("task_id")
    p.add_argument("summary")

    p = sub.add_parser("fail-task", help="record a failed attempt")
    p.add_argument("slug")
    p.add_argument("task_id")
    p.add_argument("reason")

    p = sub.add_parser("set-stage", help="set a stage's status")
    p.add_argument("slug")
    p.add_argument("stage", choices=store.STAGES)
    p.add_argument("status", choices=store.STAGE_STATUSES)

    p = sub.add_parser("validate", help="check a file or folder")
    p.add_argument("slug")
    p.add_argument("what", choices=VALIDATE_TARGETS)
    p.add_argument("--id", help="task or entity type id, for 'entity' and 'raw'")

    p = sub.add_parser("promote-entity", help="validate a roster and copy it into knowledge/entities/")
    p.add_argument("slug")
    p.add_argument("type_id")

    p = sub.add_parser("snapshot", help="record knowledge/ before dispatching researchers")
    p.add_argument("slug")

    p = sub.add_parser("check-snapshot", help="report any change to knowledge/ since the snapshot")
    p.add_argument("slug")

    p = sub.add_parser("score", help="score the branches of a finished wave")
    p.add_argument("slug")
    p.add_argument("--apply", action="store_true", help="close dry branches and return the gate summary")

    p = sub.add_parser("reopen-branch", help="reopen a closed branch")
    p.add_argument("slug")
    p.add_argument("branch")

    p = sub.add_parser("status", help="status of one subject, or of all of them")
    p.add_argument("slug", nargs="?")
    return parser


def dispatch(args):
    """Return (result, exit_code)."""
    if args.command == "scaffold":
        return store.scaffold(args.root, args.subject, args.slug), 0
    if args.command == "status" and not args.slug:
        names = store.list_workspaces(args.root)
        return {"subjects": [report.status(store.workspace(args.root, n)) for n in names]}, 0

    ws = store.workspace(args.root, args.slug)
    if args.command == "status":
        return report.status(ws), 0
    if args.command == "approve":
        return tasks.approve(ws, args.what), 0
    if args.command == "add-session":
        return tasks.add_session(ws, args.stage), 0
    if args.command == "next-task":
        return tasks.next_tasks(ws, args.limit), 0
    if args.command == "complete-task":
        return tasks.complete_task(ws, args.task_id, args.summary), 0
    if args.command == "fail-task":
        return tasks.fail_task(ws, args.task_id, args.reason), 0
    if args.command == "set-stage":
        return store.set_stage(ws, args.stage, args.status), 0
    if args.command == "validate":
        issues = run_validate(ws, args)
        ok = not validate.has_errors(issues)
        return {"ok": ok, "issues": issues}, 0 if ok else 1
    if args.command == "promote-entity":
        result = tasks.promote_entity(ws, args.type_id)
        return result, 0 if result["promoted"] else 1
    if args.command == "snapshot":
        return guard.snapshot(ws), 0
    if args.command == "check-snapshot":
        result = guard.check_snapshot(ws)
        return result, 0 if result["clean"] else 1
    if args.command == "score":
        result = scoring.score_session(ws)
        return (scoring.apply_score(ws, result) if args.apply else result), 0
    if args.command == "reopen-branch":
        return scoring.reopen_branch(ws, args.branch), 0
    raise store.RRError(f"unknown command {args.command!r}")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        result, code = dispatch(args)
    except store.RRError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run the whole suite**

Run: `python -m unittest discover -s tests`
Expected: `Ran 96 tests` and `OK`

- [ ] **Step 7: Try the script by hand**

Run: `python scripts/rr.py --root .tmp-research scaffold "Smoke Test"`
Expected: JSON with `"slug": "smoke-test"`.

Run: `python scripts/rr.py --root .tmp-research status smoke-test`
Expected: JSON whose `next_step` starts with `Complete plan.json`.

Then delete the `.tmp-research` folder.

- [ ] **Step 8: Commit**

```bash
git add scripts/rrlib/guard.py scripts/rr.py tests/test_guard.py tests/test_cli.py
git commit -m "Add the knowledge guard and the rr command line"
```
