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
    if (ws / "plan.json").exists():
        raise RRError(f"{ws.as_posix()} already exists; resume it or pass a different --slug")
    # A folder without plan.json is left over from an interrupted scaffold; finish it.
    for sub in ("knowledge/entities", "knowledge/tree", "sessions"):
        (ws / sub).mkdir(parents=True, exist_ok=True)
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
