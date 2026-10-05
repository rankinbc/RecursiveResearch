"""The mechanical part of consolidation: list what is still unknown and what conflicts."""
import re
from pathlib import Path

HEADING = "## Open at the end"
MAX_CONFLICTS = 20


def consolidate(ws):
    """Record unticked Known Unknowns in remaining_unknowns.md and list CONFLICT lines.

    Safe to run again: the 'Open at the end' section is rebuilt each time.
    """
    ws = Path(ws)
    unknowns, conflicts = [], []
    for path in sorted((ws / "knowledge" / "tree").rglob("*.md")):
        rel = path.relative_to(ws).as_posix()
        in_unknowns = False
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if "CONFLICT" in line:
                conflicts.append({"file": rel, "line": number, "text": line.strip()[:200]})
            if line.startswith("#"):
                in_unknowns = line.strip() == "## Known Unknowns"
            elif in_unknowns:
                match = re.match(r"\s*- \[ \] (.+)", line)
                if match:
                    unknowns.append((match.group(1).strip(), rel))

    target = ws / "knowledge" / "remaining_unknowns.md"
    existing = target.read_text(encoding="utf-8-sig") if target.is_file() else "# Remaining unknowns\n"
    if HEADING in existing:
        existing = existing[:existing.index(HEADING)].rstrip() + "\n"
    new = [(item, rel) for item, rel in unknowns if f"- {item}\n" not in existing]
    section = "".join(f"- {item} ({rel})\n" for item, rel in new) or "- none\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{existing}\n{HEADING}\n\n{section}", encoding="utf-8", newline="\n")
    return {"open_unknowns": len(new), "conflict_count": len(conflicts),
            "conflicts": conflicts[:MAX_CONFLICTS]}
