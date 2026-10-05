"""Checks on every file an agent or the user writes. Each returns a list of issues."""
import re
from pathlib import Path

from .provenance import MAPPED_TIERS, TIERS, scan_markdown
from .store import RRError, read_json, read_text, type_id

VERDICTS = ("exhausted", "irreducible", "sufficient", "continue")
PROPOSAL_STATUSES = ("proposed", "approved", "skipped", "dropped")
GENERIC_NAMES = ("data.json", "notes.md")
ID_RE = re.compile(r"[A-Za-z0-9_-]+")
# Wording that asks for "more" without naming what is missing. "further" and
# "deeper" only count after a research verb, so "whether further retries occur" passes.
VAGUE_RE = re.compile(
    r"^\W*(research|investigate|explore|look into|learn|study|find out)\b.*\b(further|deeper|more)\b"
    r"|\bmore (detail|details|information|research|about)\b"
    r"|\bin (more|greater) (detail|depth)\b",
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
        elif finding["tier"] == "PRIMARY" and not _text(finding.get("quote")):
            issues.append(issue("error", where,
                                "a PRIMARY finding needs a quote: the exact words copied from the source"))
        if not _text(finding.get("source")):
            issues.append(issue("error", where, "needs a source"))
    for key in ("unknowns_resolved", "unknowns_opened", "unknowns_remaining", "sources_searched", "proposals"):
        if not isinstance(doc.get(key, []), list):
            issues.append(issue("error", key, "must be a list"))
    if verdict == "exhausted" and doc.get("unknowns_remaining"):
        issues.append(issue("error", "verdict", "exhausted is not allowed while unknowns_remaining is non-empty"))
    if verdict == "exhausted" and not findings and not doc.get("unknowns_resolved"):
        issues.append(issue("error", "verdict", "exhausted means the unknown was resolved, but there are no findings "
                            "and nothing under unknowns_resolved; if the sources could not answer, use irreducible"))
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
        elif branch in closed:
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
        elif "## Known Unknowns" not in read_text(readme):
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
            meta = meta if isinstance(meta, dict) else {}
            missing = []
            if meta.get("provenance") not in TIERS:
                missing.append(f"_meta.provenance set to one of {', '.join(TIERS)}")
            if meta.get("provenance") != "UNKNOWN" and not _text(meta.get("source")):
                missing.append("_meta.source saying where the values came from")
            if missing:
                issues.append(issue("error", rel, "needs " + " and ".join(missing)))
        elif path.suffix == ".md":
            scan = scan_markdown(read_text(path))
            if not sum(scan["counts"].values()):
                level = "warning" if path.name == "README.md" else "error"
                issues.append(issue(level, rel, "contains no provenance tags"))
            for tag in scan["unknown_tags"]:
                issues.append(issue("warning", rel, f"[{tag}] is not a provenance tier"))
    return issues
