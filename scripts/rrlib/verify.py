"""Check each PRIMARY quote against the source it cites.

A researcher reads the web through tools that return a model's summary, so a
"quote" can be a sentence the page never contained. After a research task, the
script opens each PRIMARY finding's source itself and looks for the quoted
words. A finding whose quote is not there is downgraded to SECONDARY, with the
reason recorded on it.
"""
import hashlib
import html
import re
import urllib.request
from pathlib import Path

from .store import RRError, read_json, read_text, write_json, write_text

MIN_QUOTE = 20          # normalized characters; anything shorter could match by accident
MAX_BYTES = 5_000_000
TIMEOUT = 20
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
_TYPOGRAPHY = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                             "–": "-", "—": "-", " ": " "})


def normalize(text):
    """Reduce text to what a quote must match: no markup, plain quotes, single spaces, one case."""
    text = re.sub(r"<[^>]+>", " ", html.unescape(text))
    return re.sub(r"\s+", " ", text.translate(_TYPOGRAPHY)).strip().lower()


def _http_get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "recursive-research quote check"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = response.read(MAX_BYTES)
        charset = response.headers.get_content_charset() or "utf-8"
    return data.decode(charset, "replace")


FETCH = _http_get  # replaced in tests


def _fetch_cached(sources, url):
    """Return (text, error). Each URL is fetched once per session and kept on disk."""
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


def _locate(ws, finding):
    """Where the script can read this finding's source: ('file', path), ('url', url) or None."""
    local = finding.get("source_file")
    if isinstance(local, str) and local.strip():
        for candidate in (Path(local), Path(ws) / local):
            if candidate.is_file():
                return "file", candidate
    url = finding.get("source_url")
    if isinstance(url, str) and url.strip().lower().startswith(("http://", "https://")):
        return "url", url.strip()
    match = URL_RE.search(str(finding.get("source", "")))
    if match:
        return "url", match.group(0).rstrip(".,;")
    return None


def _problem(ws, sources, finding):
    """Why this quote cannot be confirmed, or None if it is in the source."""
    quote = normalize(str(finding.get("quote", "")))
    if len(quote) < MIN_QUOTE:
        return f"the quote is too short to check (under {MIN_QUOTE} characters)"
    where = _locate(ws, finding)
    if where is None:
        return ("no source the script can open was given; "
                "it needs source_url, a web address in source, or source_file")
    if where[0] == "file":
        try:
            text = read_text(where[1])
        except RRError as e:
            return f"the source file could not be read: {e}"
    else:
        text, error = _fetch_cached(sources, where[1])
        if error:
            return f"the source could not be fetched: {error}"
    if quote not in normalize(text):
        return "the quote was not found in the cited source"
    return None


def verify_result(ws, session, task_id):
    """Verify the PRIMARY findings of one research result, rewriting the file with the outcome."""
    session_dir = Path(ws) / "sessions" / session
    path = session_dir / "raw" / f"{task_id}.json"
    doc = read_json(path)
    verified = downgraded = 0
    notes = []
    for index, finding in enumerate(doc.get("findings", [])):
        if not isinstance(finding, dict):
            continue
        # a finding downgraded on an earlier run is checked again, so the result is repeatable
        if finding.get("tier") != "PRIMARY" and finding.get("downgraded_from") != "PRIMARY":
            continue
        problem = _problem(ws, session_dir / "sources", finding)
        if problem is None:
            finding["tier"] = "PRIMARY"
            finding["verified"] = True
            finding.pop("downgraded_from", None)
            finding.pop("verify_note", None)
            verified += 1
        else:
            finding["tier"] = "SECONDARY"
            finding["downgraded_from"] = "PRIMARY"
            finding["verified"] = False
            finding["verify_note"] = problem
            downgraded += 1
            notes.append({"finding": index, "note": problem})
    write_json(path, doc)
    return {"task": task_id, "verified": verified, "downgraded": downgraded, "notes": notes}
