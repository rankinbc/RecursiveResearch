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
