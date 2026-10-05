"""The fixed provenance tiers and how to find their tags in Markdown."""
import re

# Strongest first. UNKNOWN is a valid tag but never wins a conflict.
TIERS = ("PRIMARY", "EXPERT", "SECONDARY", "INFERRED", "OBSERVED", "UNKNOWN")
WEAK = ("INFERRED", "OBSERVED")
MAPPED_TIERS = ("PRIMARY", "EXPERT", "SECONDARY")

# [PRIMARY], [UNKNOWN: est 3-5] or [PRIMARY: "exact quote" https://address]. Group 2 is the
# text after the colon, which may wrap across lines. The lookahead skips links like [API](url).
TAG_RE = re.compile(r"\[([A-Z][A-Z_]+)(?::([^\]]*))?\](?!\()")


def stronger(a, b):
    """Return whichever of two tiers wins a conflict."""
    return a if TIERS.index(a) <= TIERS.index(b) else b


def scan_markdown(text):
    counts = {tier: 0 for tier in TIERS}
    unknown_tags = []
    for match in TAG_RE.finditer(text):
        tag = match.group(1)
        if tag in counts:
            counts[tag] += 1
        elif tag not in unknown_tags:
            unknown_tags.append(tag)
    return {"counts": counts, "unknown_tags": unknown_tags}
