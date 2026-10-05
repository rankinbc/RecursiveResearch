"""Sessions and their task lists: create, hand out, complete, fail."""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from .store import (RRError, STAGES, load_plan, read_json, save_plan, today, type_id, write_json,
                    write_text)
from . import verify
from .validate import (ID_RE, find_type, has_errors, validate_entity_file, validate_entity_schema,
                       validate_plan, validate_proposals, validate_raw, validate_tree)

# What the user approves at the plan gate. Controls and bookkeeping may change afterwards.
APPROVED_FIELDS = ("goal", "voice", "precision_bar", "definition_of_done", "survey_tasks", "entity_types",
                   "provenance_mapping")
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


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _plan_digests(plan):
    return {field: _digest(plan.get(field)) for field in APPROVED_FIELDS}


def approve(ws, what):
    """Record a user approval and what exactly was approved. Refuses while it is invalid."""
    plan = load_plan(ws)
    if what == "plan":
        issues = validate_plan(plan)
        seen = _plan_digests(plan)
    elif what == "entity_types":
        schema = read_json(Path(ws) / "knowledge" / "entities.json")
        issues = validate_entity_schema(schema)
        seen = _digest(schema)
    else:
        raise RRError(f"cannot approve {what!r}; expected plan or entity_types")
    if has_errors(issues):
        raise RRError(f"cannot approve {what}: {_errors(issues)}")
    plan["approvals"][what] = True
    plan["approvals"][f"{what}_seen"] = seen
    save_plan(ws, plan)
    return {"approved": what}


def require_plan_approval(plan):
    """Refuse to go on unless the plan is approved and is still the plan the user approved."""
    if not plan["approvals"]["plan"]:
        raise RRError("the plan is not approved yet; no research may start")
    seen = plan["approvals"].get("plan_seen")
    if not isinstance(seen, dict):
        return  # approved before changes were tracked
    changed = [field for field, digest in _plan_digests(plan).items() if seen.get(field) != digest]
    if changed:
        raise RRError(f"plan.json has changed since the user approved it: {', '.join(changed)}. "
                      "Show the user the change, then run approve again")


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
    require_plan_approval(plan)
    for earlier in STAGES[:STAGES.index(stage)]:
        if plan["stages"][earlier] != "done":
            raise RRError(f"the {earlier} stage is not done yet; stages run in order")
    if stage == "entity_enumeration":
        if not plan["approvals"]["entity_types"]:
            raise RRError("the entity type list is not approved yet")
        seen = plan["approvals"].get("entity_types_seen")
        if seen and seen != _digest(read_json(Path(ws) / "knowledge" / "entities.json")):
            raise RRError("knowledge/entities.json has changed since the user approved it. "
                          "Show the user the list again, then run approve again")
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
    if name in plan["sessions"]:
        raise RRError(f"session {name} already exists")
    if sdir.exists():
        # Not listed in the plan, so an earlier add-session was interrupted before it finished.
        shutil.rmtree(sdir)

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
            "dispatched": None,
        })

    (sdir / "raw").mkdir(parents=True)
    (sdir / "proposals").mkdir()
    write_json(sdir / "tasks.json", {"session": name, "stage": stage, "tasks": filled})
    write_text(sdir / "activity.md", f"# Activity log -- {plan['subject']} -- {stage}\n\n")
    plan["sessions"].append(name)
    plan["stages"][stage] = "in_progress"
    save_plan(ws, plan)
    return {"session": name, "stage": stage, "task_count": len(filled)}


def _blocked(task):
    return not task["passes"] and task["attempts"] >= MAX_ATTEMPTS


def next_tasks(ws, limit=None, session=None, mark=False):
    """The next batch to dispatch. A solo task is only ever returned on its own.

    With mark=True the batch is recorded as handed out, so the progress view can
    show those tasks as running. Reads that are only looking must leave it False.
    """
    session = session or current_session(ws)
    doc = load_tasks(ws, session)
    if mark:
        require_plan_approval(load_plan(ws))
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
    if mark and batch:
        stamp = datetime.now().isoformat(timespec="seconds")
        for task in batch:
            task["dispatched"] = stamp
        write_json(session_dir(ws, session) / "tasks.json", doc)
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
    stage = doc["stage"]
    quotes = None
    if stage == "entity_schema":
        issues = validate_entity_schema(read_json(output))
        if has_errors(issues):
            raise RRError(f"{task['output']} is not a valid entity schema: {_errors(issues)}")
    elif stage == "entity_enumeration":
        if not (Path(ws) / "knowledge" / "entities" / f"{task_id}.json").is_file():
            raise RRError(f"the roster for {task_id} is not in knowledge/entities/; "
                          "run promote-entity and fix what it reports first")
    elif stage == "deepening" and "/raw/" in task["output"]:
        raw = read_json(output)
        issues = validate_raw(raw, task_id)
        if has_errors(issues):
            raise RRError(f"{task['output']} is not a valid result: {_errors(issues)}")
        task["verdict"] = raw["verdict"]
        quotes = verify.verify_result(ws, session, task_id)
    elif stage == "deepening":
        issues = validate_tree(Path(ws) / "knowledge" / "tree")
        if has_errors(issues):
            raise RRError(f"the knowledge tree is not valid: {_errors(issues)}")
    task["passes"] = True
    task["last_error"] = None
    write_json(session_dir(ws, session) / "tasks.json", doc)
    if stage == "survey" and "/raw/" in task["output"]:
        quotes = {**verify.verify_markdown(ws, output), "notes": []}
    if "/raw/" not in task["output"]:
        verify.sweep(ws)  # an organizer has just written to knowledge/
    result = {"completed": task_id, "verdict": task["verdict"],
              "remaining": sum(1 for t in doc["tasks"] if not t["passes"])}
    if quotes and (quotes["verified"] or quotes["downgraded"]):
        plural = "" if quotes["verified"] == 1 else "s"
        summary += f" ({quotes['verified']} quote{plural} verified, {quotes['downgraded']} downgraded)"
    if quotes:
        result.update(quotes_verified=quotes["verified"], quotes_downgraded=quotes["downgraded"],
                      quote_notes=quotes["notes"])
    _log(ws, session, f"{task_id}: {summary}")
    return result


def fail_task(ws, task_id, reason, session=None):
    session = session or current_session(ws)
    doc = load_tasks(ws, session)
    task = _find(doc, task_id)
    if task["passes"]:
        raise RRError(f"task {task_id} is already complete")
    task["attempts"] += 1
    task["last_error"] = reason
    task["dispatched"] = None
    write_json(session_dir(ws, session) / "tasks.json", doc)
    _log(ws, session, f"{task_id}: FAILED (attempt {task['attempts']}): {reason}")
    return {"failed": task_id, "attempts": task["attempts"], "blocked": _blocked(task)}


def retry_task(ws, task_id, session=None):
    """Give a failed or blocked task a fresh set of attempts, when the user asks for it."""
    session = session or current_session(ws)
    doc = load_tasks(ws, session)
    task = _find(doc, task_id)
    if task["passes"]:
        raise RRError(f"task {task_id} is already complete")
    task["attempts"] = 0
    task["dispatched"] = None
    write_json(session_dir(ws, session) / "tasks.json", doc)
    _log(ws, session, f"{task_id}: attempts reset for a retry")
    return {"retry": task_id, "attempts": 0}


def decide_proposals(ws, approve=(), skip=(), approve_all=False, session=None):
    """Record the user's decisions on a gate's proposals in one call."""
    session = session or current_session(ws)
    files = sorted((session_dir(ws, session) / "proposals").glob("*.json"))
    docs = [(path, read_json(path)) for path in files]
    status = {p.get("id"): p.get("status") for _, doc in docs for p in doc.get("proposals", [])}
    for pid in [*approve, *skip]:
        if pid not in status:
            raise RRError(f"there is no proposal {pid!r} in {session}")
        if status[pid] == "dropped":
            raise RRError(f"proposal {pid} was dropped because its branch closed; reopen the branch first")
    counts = {"approved": 0, "skipped": 0, "proposed": 0}
    for path, doc in docs:
        for p in doc.get("proposals", []):
            if p.get("status") not in ("proposed", "approved"):
                continue
            if p["id"] in skip:
                p["status"] = "skipped"
                counts["skipped"] += 1
            elif approve_all or p["id"] in approve or p["status"] == "approved":
                p["status"] = "approved"
                counts["approved"] += 1
            else:
                counts["proposed"] += 1
        write_json(path, doc)
    plan = load_plan(ws)
    issues = [i for _, doc in docs for i in validate_proposals(doc, plan)]
    return {**counts, "issues": issues}


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
    verify.sweep(ws)
    checked = verify.record_for(ws, target)
    return {"promoted": True, "file": f"knowledge/entities/{tid}.json", "issues": issues,
            "quotes_verified": checked["verified"], "quotes_downgraded": checked["downgraded"]}
