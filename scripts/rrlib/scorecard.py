"""How much the knowledge base holds, and how well supported it is."""
import re
from pathlib import Path

from .provenance import TIERS, scan_markdown
from .store import RRError, load_plan, read_json, read_text
from .verify import is_checked

OVERVIEW = "(overview)"
OPEN_RE = re.compile(r"^\s*- \[ \] ", re.MULTILINE)
DONE_RE = re.compile(r"^\s*- \[[xX]\] ", re.MULTILINE)


def _empty():
    return {"claims": 0, "tiers": {tier: 0 for tier in TIERS}, "verified": 0, "unverified_primary": 0,
            "unknowns_open": 0, "unknowns_resolved": 0, "conflicts": 0, "files": 0}


def _add(total, part):
    for key in ("claims", "verified", "unverified_primary", "unknowns_open", "unknowns_resolved",
                "conflicts", "files"):
        total[key] += part[key]
    for tier in TIERS:
        total["tiers"][tier] += part["tiers"][tier]


def _count(card, tier, checked):
    card["claims"] += 1
    card["tiers"][tier] += 1
    if tier == "PRIMARY":
        card["verified" if checked else "unverified_primary"] += 1


def _unknowns_section(text):
    """The text under '## Known Unknowns', where the checklist of missing facts lives."""
    match = re.search(r"^## Known Unknowns\s*$(.*?)(?=^#|\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def _markdown(ws, path):
    card = _empty()
    card["files"] = 1
    text = read_text(path)
    checked = is_checked(ws, path)
    for tier, n in scan_markdown(text)["counts"].items():
        for _ in range(n):
            _count(card, tier, checked)
    section = _unknowns_section(text)
    card["unknowns_open"] = len(OPEN_RE.findall(section))
    card["unknowns_resolved"] = len(DONE_RE.findall(section))
    card["conflicts"] = sum(1 for line in text.splitlines() if "CONFLICT" in line)
    return card


def _tiered_entries(node, found):
    if isinstance(node, dict):
        if node.get("tier") in TIERS:
            found.append(node)
        for key, value in node.items():
            if key != "_meta":
                _tiered_entries(value, found)
    elif isinstance(node, list):
        for value in node:
            _tiered_entries(value, found)


def _json_leaf(ws, path):
    card = _empty()
    card["files"] = 1
    try:
        doc = read_json(path)
    except RRError:
        return card
    checked = is_checked(ws, path)
    entries = []
    _tiered_entries(doc, entries)
    for entry in entries:
        _count(card, entry["tier"], checked)
    meta = doc.get("_meta") if isinstance(doc, dict) else None
    # a leaf whose values carry no tiers of their own counts once, at its file-level tier
    if not entries and isinstance(meta, dict) and meta.get("provenance") in TIERS:
        _count(card, meta["provenance"], checked)
    return card


def _roster(ws, path):
    card = _empty()
    card["files"] = 1
    try:
        doc = read_json(path)
    except RRError:
        return None
    checked = is_checked(ws, path)
    entities = [e for e in doc.get("entities", []) if isinstance(e, dict) and isinstance(e.get("properties"), dict)]
    for entity in entities:
        given = entity.get("provenance")
        for name in entity["properties"]:
            tier = given if isinstance(given, str) else (given or {}).get(name)
            if tier in TIERS:
                _count(card, tier, checked)
    card["name"] = doc.get("entity_type") or path.stem
    card["type"] = path.stem
    card["instances"] = len(entities)
    return card


def scorecard(ws):
    ws = Path(ws)
    plan = load_plan(ws)
    knowledge = ws / "knowledge"

    survey = _markdown(ws, knowledge / "spec.md") if (knowledge / "spec.md").is_file() else _empty()

    catalogue = []
    for path in sorted((knowledge / "entities").glob("*.json")):
        card = _roster(ws, path)
        if card:
            catalogue.append(card)

    tree = knowledge / "tree"
    grouped = {}
    for path in sorted(p for p in tree.rglob("*") if p.is_file() and p.suffix in (".md", ".json")):
        parts = path.relative_to(tree).parts
        name = parts[0] if len(parts) > 1 else OVERVIEW
        part = _markdown(ws, path) if path.suffix == ".md" else _json_leaf(ws, path)
        _add(grouped.setdefault(name, _empty()), part)

    branches = []
    for name, card in sorted(grouped.items()):
        records = {b: r for b, r in plan["branches"].items() if b == name or b.startswith(name + "/")}
        statuses = {r.get("status") for r in records.values()}
        if name == OVERVIEW:
            status = ""
        elif not records:
            status = "not started"
        else:
            status = "open" if "open" in statuses else "closed"
        card.update(branch=name, status=status,
                    depth=max((r.get("level", 0) for r in records.values()), default=0),
                    closed=[{"branch": b, "reason": r.get("reason", "")}
                            for b, r in sorted(records.items()) if r.get("status") == "closed"])
        branches.append(card)

    overall = _empty()
    for part in [survey, *catalogue, *branches]:
        _add(overall, part)
    overall["verified_share"] = round(overall["verified"] / overall["claims"], 3) if overall["claims"] else 0.0
    return {"subject": plan["subject"], "slug": plan["slug"], "overall": overall, "survey": survey,
            "catalogue": catalogue, "branches": branches}
