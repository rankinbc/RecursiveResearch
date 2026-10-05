"""Detect writes to knowledge/ during a research batch, when only raw/ may change."""
import hashlib
from pathlib import Path

from .store import read_json, write_json
from .tasks import current_session, session_dir

SNAPSHOT = "knowledge_snapshot.json"


def _hashes(ws):
    knowledge = Path(ws) / "knowledge"
    return {p.relative_to(ws).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(knowledge.rglob("*")) if p.is_file()}


def snapshot(ws):
    """Record the state of knowledge/ before researchers are dispatched."""
    session = current_session(ws)
    hashes = _hashes(ws)
    write_json(session_dir(ws, session) / SNAPSHOT, hashes)
    return {"session": session, "files": len(hashes)}


def check_snapshot(ws):
    """Compare knowledge/ with the last snapshot. Any difference is a violation."""
    session = current_session(ws)
    before = read_json(session_dir(ws, session) / SNAPSHOT)
    after = _hashes(ws)
    violations = sorted(
        [{"file": f, "change": "added"} for f in after if f not in before]
        + [{"file": f, "change": "removed"} for f in before if f not in after]
        + [{"file": f, "change": "modified"} for f in after if f in before and after[f] != before[f]],
        key=lambda v: v["file"],
    )
    return {"session": session, "clean": not violations, "violations": violations}
