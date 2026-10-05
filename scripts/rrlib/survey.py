"""Join the survey's raw sections into knowledge/spec.md, so no agent has to retype them."""
import re
from pathlib import Path

from .store import RRError, load_plan, read_text, write_text
from .tasks import load_tasks


def _anchor(heading):
    """The link target GitHub-style Markdown gives a heading."""
    return re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")


def assemble_survey(ws, force=False):
    plan = load_plan(ws)
    session = next((s for s in plan["sessions"] if s.endswith("_survey")), None)
    if session is None:
        raise RRError("there is no survey session to assemble")
    target = Path(ws) / "knowledge" / "spec.md"
    if target.is_file() and target.stat().st_size and not force:
        raise RRError("knowledge/spec.md already exists; pass --force to rebuild it and lose any edits")

    sections, missing = [], []
    for task in load_tasks(ws, session)["tasks"]:
        if task["solo"]:
            continue
        path = Path(ws) / task["output"]
        if not task["passes"] or not path.is_file():
            missing.append(task["title"])
            continue
        body = read_text(path).strip()
        match = re.search(r"^## +(.+)$", body, re.MULTILINE)
        if match:
            heading = match.group(1).strip()
        else:
            heading = task["title"]
            body = f"## {heading}\n\n{body}"
        sections.append((heading, body))
    if not sections:
        raise RRError("no completed survey sections to assemble")

    contents = "\n".join(f"- [{heading}](#{_anchor(heading)})" for heading, _ in sections)
    text = f"# {plan['subject']} -- Survey\n\n## Contents\n\n{contents}\n\n"
    text += "\n\n".join(body for _, body in sections) + "\n"
    if missing:
        text += "\n## Missing sections\n\n" + "".join(f"- {title}\n" for title in missing)
    write_text(target, text)
    return {"file": "knowledge/spec.md", "sections": len(sections), "missing": missing,
            "lines": text.count("\n")}
