"""Decide which branches of the knowledge tree have run dry, and close them."""
from pathlib import Path

from .provenance import WEAK
from .store import RRError, load_plan, read_json, read_text, save_plan, write_json
from .tasks import MAX_ATTEMPTS, current_session, load_tasks, session_dir

DISPOSITIONS = ("new", "duplicate", "conflict")
GATE = "gate.json"  # written when a session has been scored and its gate can be presented
# When no researcher on a branch said "continue", report the most informative reason
VERDICT_PRIORITY = ("irreducible", "sufficient", "exhausted")


def _recommend(b, thresholds, depth_cap):
    if not b["completed"]:
        return "blocked", "no task on this branch completed"
    if "continue" not in b["verdicts"]:
        return "close", next(v for v in VERDICT_PRIORITY if v in b["verdicts"])
    # A task is asked to resolve one unknown, so a small count alone is not a dry branch.
    if b["new"] < thresholds["min_new_facts"] and b["unknowns_resolved"] == 0:
        return "close", f"diminishing returns: only {b['new']} new facts and no unknowns resolved"
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


def _pending(ws, session):
    """Proposals still awaiting a decision or a wave, without their long descriptions."""
    return [{"id": p.get("id"), "title": p.get("title"), "unknown": p.get("unknown_being_resolved"),
             "sources": p.get("expected_sources"), "branch": p.get("branch"), "level": p.get("level"),
             "status": p.get("status")}
            for path in _proposal_files(ws, session)
            for p in read_json(path).get("proposals", []) if p.get("status") in ("proposed", "approved")]


def _gate_summary(ws, session, names, blocked, dropped, already_applied):
    """Describe the gate from what is on disk now, so reopened branches show as open."""
    plan = load_plan(ws)
    closed, still_open = [], []
    for name in sorted(names):
        record = plan["branches"].get(name, {})
        if record.get("status") == "closed":
            closed.append({"branch": name, "reason": record.get("reason", "")})
        elif name not in blocked:
            still_open.append(name)
    pending = _pending(ws, session)
    return {"session": session, "closed": closed, "open": still_open, "blocked": sorted(blocked),
            "proposals_dropped": dropped, "proposals_pending": len(pending), "proposals": pending,
            "agents_per_batch": plan["controls"]["max_agents_per_wave"],
            "already_applied": already_applied}


def apply_score(ws, result):
    """Close the branches recommended for closing and build the gate summary.

    Runs once per session. Every step can be repeated after an interruption, and
    gate.json, written last, marks the session as scored: after that, running
    this again only reports, so it cannot undo a reopen.
    """
    session = result["session"]
    gate_path = session_dir(ws, session) / GATE
    if gate_path.is_file():
        gate = read_json(gate_path)
        return _gate_summary(ws, session, gate["branches"], gate["blocked"], gate["proposals_dropped"], True)

    to_close = sorted(n for n, b in result["branches"].items() if b["recommendation"] == "close")
    blocked = sorted(n for n, b in result["branches"].items() if b["recommendation"] == "blocked")

    path = Path(ws) / "knowledge" / "remaining_unknowns.md"
    existing = read_text(path) if path.is_file() else ""
    text = "" if existing else "# Remaining unknowns\n"
    for name in to_close:
        b = result["branches"][name]
        heading = f"\n## {name}\n\nClosed in {session}: "
        if heading in existing:
            continue
        text += f"{heading}{b['reason']}\n\n"
        text += "".join(f"- {u}\n" for u in b["remaining"]) or "- none recorded\n"
    if text and (to_close or existing):
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(text)

    plan = load_plan(ws)
    for name, b in result["branches"].items():
        if name in to_close:
            plan["branches"][name] = {"status": "closed", "reason": b["reason"],
                                      "session": session, "level": b["level"]}
        else:
            plan["branches"][name] = {"status": "open", "level": b["level"]}
    save_plan(ws, plan)

    all_closed = [name for name, b in plan["branches"].items() if b["status"] == "closed"]
    dropped = 0
    for proposals in _proposal_files(ws, session):
        doc = read_json(proposals)
        changed = False
        for p in doc.get("proposals", []):
            # Exact match only: a sub-branch is its own branch and may still be productive.
            if p.get("status") in ("proposed", "approved") and p.get("branch") in all_closed:
                p["status"] = "dropped"
                p["dropped_reason"] = "branch closed"
                dropped += 1
                changed = True
        if changed:
            write_json(proposals, doc)

    write_json(gate_path, {"branches": sorted(result["branches"]), "blocked": blocked,
                           "proposals_dropped": dropped})
    return _gate_summary(ws, session, result["branches"], blocked, dropped, False)


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
            if p.get("status") == "dropped" and p.get("branch") == branch:
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
