"""A readable view of how far a research project has got, built only from files on disk."""
from pathlib import Path

from .report import status
from .scorecard import scorecard
from .scoring import DISPOSITIONS, GATE
from .store import RRError, STAGES, load_plan, read_json
from .tasks import MAX_ATTEMPTS, load_tasks, session_dir


def _state(task):
    if task["passes"]:
        return "done"
    if task["attempts"] >= MAX_ATTEMPTS:
        return "blocked"
    if task.get("dispatched"):
        return "running"
    return "retry" if task["attempts"] else "pending"


def _wave(ws, name, doc):
    """Counts for one deepening wave, from whatever has come back so far."""
    sdir = session_dir(ws, name)
    row = {"session": name, "wave": name.rsplit("_", 1)[-1],
           "done": sum(1 for t in doc["tasks"] if t["passes"]), "total": len(doc["tasks"]),
           "findings": 0, "new": None, "duplicate": None, "conflict": None,
           "unknowns_resolved": 0, "unknowns_opened": 0, "scored": (sdir / GATE).is_file()}
    for task in doc["tasks"]:
        if not task["passes"]:
            continue
        try:
            raw = read_json(Path(ws) / task["output"])
        except RRError:
            continue  # a damaged result file is the validator's job to report, not this view's
        row["findings"] += len(raw.get("findings", []))
        row["unknowns_resolved"] += len(raw.get("unknowns_resolved", []))
        row["unknowns_opened"] += len(raw.get("unknowns_opened", []))
    if (sdir / "ledger.json").is_file():
        try:
            entries = read_json(sdir / "ledger.json").get("entries", [])
        except (RRError, AttributeError):
            entries = []
        for disposition in DISPOSITIONS:
            row[disposition] = sum(1 for e in entries
                                   if isinstance(e, dict) and e.get("disposition") == disposition)
    return row


def progress(ws):
    plan = load_plan(ws)
    stages = {stage: {"status": plan["stages"][stage], "done": 0, "total": 0} for stage in STAGES}
    waves, runs, session = [], 0, None
    for name in plan["sessions"]:
        doc = load_tasks(ws, name)
        stages[doc["stage"]]["total"] += len(doc["tasks"])
        stages[doc["stage"]]["done"] += sum(1 for t in doc["tasks"] if t["passes"])
        runs += sum(t["attempts"] + (1 if t["passes"] else 0) for t in doc["tasks"])
        if doc["stage"] == "deepening" and any(t["branch"] for t in doc["tasks"]):
            waves.append(_wave(ws, name, doc))
        session = {"name": name, "stage": doc["stage"],
                   "tasks": [{"id": t["id"], "title": t["title"], "state": _state(t),
                              "verdict": t["verdict"], "last_error": t["last_error"]}
                             for t in doc["tasks"]]}
    return {
        "subject": plan["subject"],
        "slug": plan["slug"],
        "workspace": Path(ws).as_posix(),
        "next_step": status(ws)["next_step"],
        "stages": stages,
        "session": session,
        "waves": waves,
        "branches": [{"branch": name, "status": b["status"], "level": b.get("level", 0),
                      "reason": b.get("reason", "")}
                     for name, b in sorted(plan["branches"].items())],
        "agent_runs": runs,
        "knowledge": scorecard(ws)["overall"],
    }


def _count(value):
    return "-" if value is None else str(value)


def render(data):
    lines = [f"{data['subject']}  ({data['workspace']})", f"Next: {data['next_step']}", "", "Stages"]
    for stage in STAGES:
        s = data["stages"][stage]
        counts = f"{s['done']}/{s['total']}" if s["total"] else "-"
        lines.append(f"  {s['status'].replace('_', ' '):<12} {stage:<20} {counts}")

    lines.append("")
    session = data["session"]
    if not session:
        lines.append("No session yet.")
    else:
        lines.append(f"Current session: {session['name']}")
        for t in session["tasks"]:
            note = ""
            if t["verdict"]:
                note = f"  ({t['verdict']})"
            elif t["last_error"]:
                note = f"  -- {t['last_error']}"
            lines.append(f"  {t['state']:<8} {t['id']:<24} {t['title']}{note}")

    if data["waves"]:
        lines += ["", "Waves",
                  f"  {'wave':<6}{'tasks':<8}{'findings':<10}{'new':<6}{'dup':<6}"
                  f"{'conflict':<10}{'resolved':<10}{'opened':<8}scored"]
        for w in data["waves"]:
            lines.append(f"  {w['wave']:<6}{str(w['done']) + '/' + str(w['total']):<8}{w['findings']:<10}"
                         f"{_count(w['new']):<6}{_count(w['duplicate']):<6}{_count(w['conflict']):<10}"
                         f"{w['unknowns_resolved']:<10}{w['unknowns_opened']:<8}"
                         f"{'yes' if w['scored'] else 'no'}")

    if data["branches"]:
        lines += ["", "Branches"]
        for b in data["branches"]:
            reason = f"  {b['reason']}" if b["reason"] else ""
            lines.append(f"  {b['status']:<7} {b['branch']:<36} level {b['level']}{reason}")

    k = data.get("knowledge")
    if k and (k["claims"] or k["unknowns_open"]):
        t = k["tiers"]
        lines += ["", "Knowledge",
                  f"  claims {k['claims']}   verified {k['verified']}   expert {t['EXPERT']}   "
                  f"secondary {t['SECONDARY']}   inferred {t['INFERRED']}   observed {t['OBSERVED']}",
                  f"  open unknowns {k['unknowns_open']}   conflicts {k['conflicts']}"]
        if k["unverified_primary"]:
            lines.append(f"  {k['unverified_primary']} PRIMARY claims not yet checked; run verify")
    lines += ["", f"Agent runs so far: {data['agent_runs']}"]
    return "\n".join(lines)
