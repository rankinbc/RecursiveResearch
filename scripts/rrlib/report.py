"""Where a research project stands and what to do next."""
from .scoring import GATE
from .store import STAGES, load_plan
from .tasks import load_tasks, next_tasks, session_dir


def _deepening_step(ws, name):
    sdir = session_dir(ws, name)
    if (sdir / GATE).is_file():
        return (f"At the gate for {name}: show the score --apply summary and the proposals. Then "
                "add-session deepening for approved proposals, or consolidate and set-stage deepening done.")
    bootstrap = not any(t["branch"] for t in load_tasks(ws, name)["tasks"])
    if bootstrap or (sdir / "ledger.json").is_file():
        return f"Validate the tree and proposals for {name}, then score --apply and present the gate."
    return f"Run the organizer for {name}, then score --apply and present the gate."


def _next_step(ws, plan, session):
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
            return _deepening_step(ws, session["name"])
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
        "next_step": _next_step(ws, plan, session),
    }
