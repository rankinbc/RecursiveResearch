#!/usr/bin/env python3
"""Bookkeeping for recursive-research. Every command prints one JSON object,
except `progress`, which prints a readable summary for a person.

Exit codes: 0 = ok, 1 = validation found errors, 2 = the command could not run.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rrlib import (briefs, consolidate, guard, progress, report, scoring, store, survey,  # noqa: E402
                   tasks, validate)

VALIDATE_TARGETS = ("plan", "entity_schema", "entity", "proposals", "raw", "tree")
MAX_ISSUES = 10


def compact_issues(ws, name, issues):
    """Counts plus the first few issues; the full list goes to a file an agent can read."""
    out = {"errors": sum(1 for i in issues if i["level"] == "error"),
           "warnings": sum(1 for i in issues if i["level"] == "warning"),
           "issues": issues[:MAX_ISSUES]}
    if len(issues) > MAX_ISSUES:
        path = ws / "issues" / f"{name}.json"
        store.write_json(path, issues)
        out["issues_file"] = path.as_posix()
    return out


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

    p = sub.add_parser("brief", help="render the brief for an organizer job that is not a task")
    p.add_argument("slug")
    p.add_argument("job", choices=tuple(briefs.JOBS))

    p = sub.add_parser("assemble-survey", help="join the raw survey sections into knowledge/spec.md")
    p.add_argument("slug")
    p.add_argument("--force", action="store_true", help="rebuild an existing spec.md, losing edits")

    p = sub.add_parser("approve-proposals", help="record the user's decisions on a gate's proposals")
    p.add_argument("slug")
    p.add_argument("ids", nargs="*", help="proposal ids to approve")
    p.add_argument("--all", action="store_true", help="approve every proposal not skipped")
    p.add_argument("--skip", nargs="*", default=[], metavar="ID", help="proposal ids to skip")

    p = sub.add_parser("consolidate", help="record open unknowns and list conflicts in the tree")
    p.add_argument("slug")

    p = sub.add_parser("retry-task", help="give a blocked task a fresh set of attempts")
    p.add_argument("slug")
    p.add_argument("task_id")

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

    p = sub.add_parser("progress", help="readable progress summary, for watching a run")
    p.add_argument("slug")
    p.add_argument("--json", action="store_true", help="print the underlying data as JSON")
    p.add_argument("--watch", nargs="?", const=5.0, type=float, metavar="SECONDS",
                   help="refresh until Ctrl+C (default every 5 seconds)")
    return parser


def run_progress(args):
    ws = store.workspace(args.root, args.slug)
    if args.json:
        print(json.dumps(progress.progress(ws), indent=2, ensure_ascii=False))
        return 0
    if args.watch is None:
        print(progress.render(progress.progress(ws)))
        return 0
    interval = max(args.watch, 1.0)
    try:
        while True:
            text = progress.render(progress.progress(ws))
            os.system("cls" if os.name == "nt" else "clear")
            print(f"{text}\n\nRefreshing every {interval:g}s. Ctrl+C to stop.", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


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
        return briefs.attach(ws, tasks.next_tasks(ws, args.limit, mark=True)), 0
    if args.command == "brief":
        return briefs.job_brief(ws, args.job), 0
    if args.command == "assemble-survey":
        return survey.assemble_survey(ws, args.force), 0
    if args.command == "consolidate":
        return consolidate.consolidate(ws), 0
    if args.command == "approve-proposals":
        result = tasks.decide_proposals(ws, args.ids, args.skip, args.all)
        result.update(compact_issues(ws, "proposals", result.pop("issues")))
        return result, 1 if result["errors"] else 0
    if args.command == "complete-task":
        return tasks.complete_task(ws, args.task_id, args.summary), 0
    if args.command == "fail-task":
        return tasks.fail_task(ws, args.task_id, args.reason), 0
    if args.command == "retry-task":
        return tasks.retry_task(ws, args.task_id), 0
    if args.command == "set-stage":
        return store.set_stage(ws, args.stage, args.status), 0
    if args.command == "validate":
        issues = run_validate(ws, args)
        ok = not validate.has_errors(issues)
        name = args.what + (f"-{args.id}" if args.id else "")
        return {"ok": ok, **compact_issues(ws, name, issues)}, 0 if ok else 1
    if args.command == "promote-entity":
        result = tasks.promote_entity(ws, args.type_id)
        result.update(compact_issues(ws, f"entity-{args.type_id}", result.pop("issues")))
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
        if args.command == "progress":
            return run_progress(args)
        result, code = dispatch(args)
    except store.RRError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as e:  # a crash must never look like a validation result (exit 1)
        message = f"internal error ({type(e).__name__}: {e}); check plan.json and the session files for wrong types"
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
