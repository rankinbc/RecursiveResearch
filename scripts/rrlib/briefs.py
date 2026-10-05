"""Render the brief each agent receives into a file.

The coordinator passes an agent only the path, so it never reads a template or
retypes one, and a placeholder can never be left unfilled or filled wrongly.
"""
import json
import re
from pathlib import Path

from .store import RRError, load_plan, read_json
from .tasks import current_session, load_tasks, session_dir
from .validate import find_type

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "skills" / "recursive-research" / "templates"
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_]+)\}\}")
JOBS = {"wave": "organize-wave.md", "consolidate": "organize-consolidate.md"}
TASK_TEMPLATES = ("research-survey.md", "organize-survey.md", "organize-schema.md",
                  "research-entity.md", "organize-bootstrap.md", "research-deepening.md")
ALL_TEMPLATES = TASK_TEMPLATES + tuple(JOBS.values())
NO_BRIEF = "No coordination brief was written for this wave."


def template_for(stage, task):
    if stage == "survey":
        return "organize-survey.md" if task["solo"] else "research-survey.md"
    if stage == "entity_schema":
        return "organize-schema.md"
    if stage == "entity_enumeration":
        return "research-entity.md"
    return "research-deepening.md" if task["branch"] else "organize-bootstrap.md"


def _agent(template):
    return "researcher" if template.startswith("research-") else "organizer"


def _base_values(ws, plan, session):
    mapping = "\n".join(f"- `{tier}`: {'; '.join(sources)}"
                        for tier, sources in plan["provenance_mapping"].items() if sources)
    closed = sorted(name for name, b in plan["branches"].items() if b.get("status") == "closed")
    return {
        "SUBJECT": plan["subject"],
        "GOAL": plan["goal"],
        "VOICE": plan["voice"],
        "PRECISION_BAR": plan["precision_bar"],
        "DEFINITION_OF_DONE": plan["definition_of_done"],
        "PROVENANCE_MAPPING": mapping or "- (no sources are mapped)",
        "EXPECTED_TYPES": ", ".join(plan["entity_types"]),
        "WORKSPACE": Path(ws).as_posix(),
        "SESSION": session,
        "DEPTH_CAP": plan["controls"]["depth_cap"],
        "CLOSED_BRANCHES": ", ".join(closed) or "none",
    }


def _coordination(ws, plan, session, doc, task):
    """The ownership lines that concern this task: its own and its branch neighbours'."""
    index = plan["sessions"].index(session)
    path = session_dir(ws, plan["sessions"][index - 1]) / "coordination_brief.md" if index else None
    if path is None or not path.is_file():
        return NO_BRIEF
    text = path.read_text(encoding="utf-8-sig").strip()
    top = task["branch"].split("/")[0]
    ids = [t["id"] for t in doc["tasks"] if t["branch"].split("/")[0] == top]
    lines = [line for line in text.splitlines() if any(i in line for i in ids)]
    return "\n".join(lines) if lines else text


def _render(template, values):
    text = (TEMPLATE_DIR / template).read_text(encoding="utf-8")
    missing = sorted(set(PLACEHOLDER_RE.findall(text)) - set(values))
    if missing:
        raise RRError(f"{template} uses placeholders that have no value: {', '.join(missing)}")
    return PLACEHOLDER_RE.sub(lambda m: str(values[m.group(1)]), text)


def _write(ws, session, name, text):
    path = session_dir(ws, session) / "briefs" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path.as_posix()


def task_brief(ws, task_id, session=None):
    plan = load_plan(ws)
    session = session or current_session(ws)
    doc = load_tasks(ws, session)
    task = next((t for t in doc["tasks"] if t["id"] == task_id), None)
    if task is None:
        raise RRError(f"session {session} has no task {task_id!r}")
    template = template_for(doc["stage"], task)
    values = _base_values(ws, plan, session)
    values.update({
        "TASK_ID": task["id"],
        "TASK_TITLE": task["title"],
        "TASK_DESCRIPTION": task["description"],
        "OUTPUT": task["output"],
        "UNKNOWN": task["unknown"],
        "EXPECTED_SOURCES": "; ".join(task["expected_sources"]),
        "BRANCH": task["branch"],
        "TARGET": task["target"],
    })
    if template == "research-survey.md":
        values["OTHER_TASKS"] = "\n".join(
            f"- {t['title']}" for t in doc["tasks"] if t["id"] != task_id and not t["solo"])
    elif template == "research-entity.md":
        schema_type = find_type(read_json(Path(ws) / "knowledge" / "entities.json"), task_id)
        values["TYPE_NAME"] = schema_type["name"]
        # indented so it renders as a code block
        values["TYPE_SCHEMA"] = "\n".join(
            "    " + line for line in json.dumps(schema_type, indent=2, ensure_ascii=False).splitlines())
    elif template == "research-deepening.md":
        values["BRIEF"] = _coordination(ws, plan, session, doc, task)
    return {"id": task["id"], "title": task["title"], "agent": _agent(template),
            "brief": _write(ws, session, task["id"], _render(template, values)),
            "output": task["output"]}


def job_brief(ws, job, session=None):
    """Briefs for organizer jobs that are not tasks: organizing a wave, and consolidation."""
    if job not in JOBS:
        raise RRError(f"unknown job {job!r}; expected one of {', '.join(JOBS)}")
    plan = load_plan(ws)
    session = session or current_session(ws)
    values = _base_values(ws, plan, session)
    values["NEXT_LEVEL"] = max((t["level"] for t in load_tasks(ws, session)["tasks"]), default=0) + 1
    template = JOBS[job]
    return {"job": job, "agent": _agent(template),
            "brief": _write(ws, session, f"_{job}", _render(template, values))}


def attach(ws, batch):
    """Replace the full task records in a next-task batch with ids and brief paths."""
    batch = dict(batch)
    batch["tasks"] = [task_brief(ws, t["id"], batch["session"]) for t in batch["tasks"]]
    return batch
