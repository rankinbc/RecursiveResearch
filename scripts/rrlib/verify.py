"""Check every PRIMARY claim against the source it cites.

A researcher reads the web through tools that return a model's summary, so a
"quote" can be a sentence the page never contained. The script therefore opens
each cited source itself and looks for the quoted words. A claim whose quote
is not there, or that gives nothing to check, is downgraded to SECONDARY with
the reason recorded.

After `sweep`, every PRIMARY left in the knowledge base has been confirmed.
"""
import hashlib
import html
import re
import urllib.request
from pathlib import Path

from .provenance import TAG_RE
from .store import RRError, read_json, read_text, write_json, write_text

MIN_QUOTE = 20          # normalized characters; anything shorter could match by accident
MAX_BYTES = 5_000_000
TIMEOUT = 20
LEDGER = "verification.json"
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
QUOTE_RE = re.compile(r"[\"“](.+)[\"”]", re.DOTALL)
_TYPOGRAPHY = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                             "–": "-", "—": "-", " ": " "})
NO_QUOTE = "no quote given"
# short forms, safe to write inside a Markdown tag
SHORT = (("not found", "quote not found in source"), ("too short", "quote too short to check"),
         ("no quote", NO_QUOTE), ("no source", "no source given"),
         ("could not be fetched", "source unreachable"), ("could not be read", "source unreadable"),
         ("does not contain", "quote does not contain the value"))


def normalize(text):
    """Reduce text to what a quote must match: no markup, plain quotes, single spaces, one case."""
    text = re.sub(r"<[^>]+>", " ", html.unescape(text))
    return re.sub(r"\s+", " ", text.translate(_TYPOGRAPHY)).strip().lower()


NUMBER_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*([km])?\b", re.IGNORECASE)


def _states(quote, value):
    """True if the quote contains this number, however it is written: 150000, 150,000 or 150K."""
    for digits, scale in NUMBER_RE.findall(quote):
        try:
            number = float(digits.replace(",", ""))
        except ValueError:
            continue
        number *= {"k": 1_000, "m": 1_000_000}.get(scale.lower(), 1)
        if abs(number - value) < 1e-9:
            return True
    return False


def _http_get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "recursive-research quote check"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = response.read(MAX_BYTES)
        charset = response.headers.get_content_charset() or "utf-8"
    return data.decode(charset, "replace")


FETCH = _http_get  # replaced in tests


def _fetch_cached(ws, url):
    """Return (text, error). Each address is fetched once per workspace and kept on disk."""
    sources = Path(ws) / "sources"
    index_path = sources / "index.json"
    index = read_json(index_path) if index_path.is_file() else {}
    if url not in index:
        name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ".txt"
        try:
            write_text(sources / name, FETCH(url))
            index[url] = {"file": name, "error": None}
        except Exception as e:  # any network, TLS or decoding failure means "could not check"
            index[url] = {"file": None, "error": f"{type(e).__name__}: {e}"[:200]}
        write_json(index_path, index)
    entry = index[url]
    if entry["error"]:
        return None, entry["error"]
    return read_text(sources / entry["file"]), None


def _locate(ws, claim):
    """Where the script can read this claim's source: ('file', path), ('url', url) or None."""
    local = claim.get("source_file")
    if isinstance(local, str) and local.strip():
        for candidate in (Path(local), Path(ws) / local):
            if candidate.is_file():
                return "file", candidate
    url = claim.get("source_url")
    if isinstance(url, str) and url.strip().lower().startswith(("http://", "https://")):
        return "url", url.strip()
    match = URL_RE.search(str(claim.get("source", "")))
    if match:
        return "url", match.group(0).rstrip(".,;")
    return None


def check(ws, claim):
    """Why this claim's quote cannot be confirmed, or None if it is in the source.

    `claim` is any mapping with `quote` and one of `source_url`, `source_file`,
    or a web address inside `source`.
    """
    if not str(claim.get("quote", "")).strip():
        return NO_QUOTE
    quote = normalize(str(claim["quote"]))
    if len(quote) < MIN_QUOTE:
        return f"the quote is too short to check (under {MIN_QUOTE} characters)"
    where = _locate(ws, claim)
    if where is None:
        return ("no source the script can open was given; "
                "it needs source_url, a web address in source, or source_file")
    if where[0] == "file":
        try:
            text = read_text(where[1])
        except RRError as e:
            return f"the source file could not be read: {e}"
    else:
        text, error = _fetch_cached(ws, where[1])
        if error:
            return f"the source could not be fetched: {error}"
    if quote not in normalize(text):
        return "the quote was not found in the cited source"
    return None


def _short(problem):
    return next((short for needle, short in SHORT if needle in problem), "not confirmed")


def _settle(ws, record, key):
    """Verify one record whose tier lives under `key`. Returns 'verified', 'downgraded' or None."""
    # a record downgraded on an earlier run is checked again, so the result is repeatable
    if record.get(key) != "PRIMARY" and record.get("downgraded_from") != "PRIMARY":
        return None
    problem = check(ws, record)
    if problem is None:
        record[key] = "PRIMARY"
        record["verified"] = True
        record.pop("downgraded_from", None)
        record.pop("verify_note", None)
        return "verified"
    record[key] = "SECONDARY"
    record["downgraded_from"] = "PRIMARY"
    record["verified"] = False
    record["verify_note"] = problem
    return "downgraded"


def verify_result(ws, session, task_id):
    """Verify the PRIMARY findings of one stage 4 research result, rewriting the file."""
    path = Path(ws) / "sessions" / session / "raw" / f"{task_id}.json"
    doc = read_json(path)
    counts = {"verified": 0, "downgraded": 0}
    notes = []
    for index, finding in enumerate(doc.get("findings", [])):
        if not isinstance(finding, dict):
            continue
        outcome = _settle(ws, finding, "tier")
        if outcome:
            counts[outcome] += 1
        if outcome == "downgraded":
            notes.append({"finding": index, "note": finding["verify_note"]})
    write_json(path, doc)
    return {"task": task_id, **counts, "notes": notes}


def _walk(ws, node, counts):
    if isinstance(node, dict):
        if "tier" in node:
            outcome = _settle(ws, node, "tier")
            if outcome:
                counts[outcome] += 1
        meta = node.get("_meta")
        if isinstance(meta, dict):
            outcome = _settle(ws, meta, "provenance")
            if outcome:
                counts[outcome] += 1
        for key, value in node.items():
            if key != "_meta":
                _walk(ws, value, counts)
    elif isinstance(node, list):
        for value in node:
            _walk(ws, value, counts)


def verify_json(ws, path):
    """Verify a JSON leaf: its `_meta` block and any entry that carries its own `tier`."""
    doc = read_json(path)
    counts = {"verified": 0, "downgraded": 0}
    _walk(ws, doc, counts)
    write_json(path, doc)
    return counts


def _tag_claim(payload):
    """Read `"exact quote" address` from inside a Markdown tag."""
    match = QUOTE_RE.search(payload)
    if not match:
        return {}
    rest = payload[match.end():].strip()
    url = URL_RE.search(rest)
    claim = {"quote": match.group(1)}
    if url:
        claim["source_url"] = url.group(0).rstrip(".,;")
    elif rest:
        claim["source_file"] = rest
    return claim


def verify_markdown(ws, path):
    """Verify every `[PRIMARY: "quote" address]` tag in a Markdown file, rewriting failures."""
    counts = {"verified": 0, "downgraded": 0}

    def settle(match):
        if match.group(1) != "PRIMARY":
            return match.group(0)
        problem = check(ws, _tag_claim(match.group(2) or ""))
        if problem is None:
            counts["verified"] += 1
            return match.group(0)
        counts["downgraded"] += 1
        return f"[SECONDARY: was PRIMARY, {_short(problem)}]"

    text = read_text(path)
    checked = TAG_RE.sub(settle, text)
    if checked != text:
        write_text(path, checked)
    return counts


def verify_roster(ws, path):
    """Verify an entity roster. Each PRIMARY value needs evidence: a quote and where it is."""
    doc = read_json(path)
    counts = {"verified": 0, "downgraded": 0}
    for entity in doc.get("entities", []):
        if not isinstance(entity, dict) or not isinstance(entity.get("properties"), dict):
            continue
        properties = entity["properties"]
        given = entity.get("provenance")
        tiers = {name: given if isinstance(given, str) else (given or {}).get(name) for name in properties}
        evidence = entity.get("evidence") if isinstance(entity.get("evidence"), dict) else {}
        notes = {}
        for name, tier in tiers.items():
            if tier != "PRIMARY":
                continue
            claim = evidence.get(name) if isinstance(evidence.get(name), dict) else evidence
            problem = check(ws, claim) if "quote" in claim else NO_QUOTE
            value = properties[name]
            if (problem is None and isinstance(value, (int, float)) and not isinstance(value, bool)
                    and not _states(str(claim["quote"]), value)):
                problem = "the quote does not contain the value"
            if problem:
                tiers[name] = "SECONDARY"
                notes[name] = problem
                counts["downgraded"] += 1
            else:
                counts["verified"] += 1
        if notes:
            entity["provenance"] = tiers
            entity["verify_notes"] = notes
        entity["verified"] = sorted(name for name, tier in tiers.items() if tier == "PRIMARY")
    write_json(path, doc)
    return counts


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _targets(ws):
    knowledge = Path(ws) / "knowledge"
    files = [knowledge / "spec.md"]
    files += sorted((knowledge / "tree").rglob("*.md")) + sorted((knowledge / "tree").rglob("*.json"))
    files += sorted((knowledge / "entities").glob("*.json"))
    return [f for f in files if f.is_file()]


def sweep(ws):
    """Verify everything in knowledge/ that has changed since it was last checked."""
    ws = Path(ws)
    ledger_path = ws / "knowledge" / LEDGER
    files = read_json(ledger_path).get("files", {}) if ledger_path.is_file() else {}
    result = {"files_checked": 0, "verified": 0, "downgraded": 0}
    current = {}
    for path in _targets(ws):
        rel = path.relative_to(ws).as_posix()
        record = files.get(rel)
        if record and record.get("hash") == _digest(path):
            current[rel] = record
            continue
        if path.suffix == ".md":
            counts = verify_markdown(ws, path)
        elif path.parent.name == "entities":
            counts = verify_roster(ws, path)
        else:
            counts = verify_json(ws, path)
        current[rel] = {"hash": _digest(path), **counts}
        result["files_checked"] += 1
        result["verified"] += counts["verified"]
        result["downgraded"] += counts["downgraded"]
    if current != files or not ledger_path.is_file():
        write_json(ledger_path, {"files": current})
    return result


def is_checked(ws, path):
    """True if this knowledge file is unchanged since the last sweep verified it."""
    ws, path = Path(ws), Path(path)
    ledger_path = ws / "knowledge" / LEDGER
    if not ledger_path.is_file() or not path.is_file():
        return False
    record = read_json(ledger_path).get("files", {}).get(path.relative_to(ws).as_posix())
    return bool(record) and record.get("hash") == _digest(path)


def record_for(ws, path):
    """The ledger entry for a knowledge file, or None."""
    ledger_path = Path(ws) / "knowledge" / LEDGER
    if not ledger_path.is_file():
        return None
    return read_json(ledger_path).get("files", {}).get(Path(path).relative_to(ws).as_posix())
