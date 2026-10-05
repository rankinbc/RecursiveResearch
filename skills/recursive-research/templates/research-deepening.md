# Research task {{TASK_ID}}: {{TASK_TITLE}}

You are researching **{{SUBJECT}}**. Resolve one specific unknown.

**The unknown:** {{UNKNOWN}}

**Context:** {{TASK_DESCRIPTION}}

**Where to look first:** {{EXPECTED_SOURCES}}

**Branch:** `{{BRANCH}}`. Your findings will be placed in `{{TARGET}}` by
another agent. Read `{{WORKSPACE}}/knowledge/tree/{{BRANCH}}/` first so you do
not report what is already there.

**Web search is required.** If the search tools are missing or fail, write
nothing and reply with the single line `SEARCH_UNAVAILABLE: <what failed>`.

## Who owns what

{{BRIEF}}

Stay inside your own task. If you find something that belongs to another
task, add it as a finding anyway and say so in the claim.

## Write

Write JSON to `{{WORKSPACE}}/{{OUTPUT}}` in exactly this shape:

    {
      "task_id": "{{TASK_ID}}",
      "branch": "{{BRANCH}}",
      "verdict": "continue",
      "verdict_reason": "",
      "findings": [
        {"claim": "The maximum frame length is 16384 bytes", "tier": "PRIMARY",
         "source": "RFC 9999, section 4.2",
         "source_url": "https://example.org/rfc9999.txt",
         "quote": "A frame MUST NOT exceed 16384 bytes.", "detail": ""}
      ],
      "unknowns_resolved": ["The maximum frame length in bytes"],
      "unknowns_opened": ["Whether extension frames may exceed the maximum"],
      "unknowns_remaining": ["Whether extension frames may exceed the maximum"],
      "sources_searched": ["RFC 9999", "vendor implementation notes"],
      "proposals": []
    }

- One finding per fact. Put formulas, pseudocode, or tables in `detail`.
- Every finding has a `tier` and a `source`. A finding cannot be `UNKNOWN`;
  list what you could not find under `unknowns_remaining`.
- `unknowns_opened` are new questions your research raised.
  `unknowns_remaining` is everything still unanswered when you stop,
  including the opened ones.

## Provenance

Tiers, strongest first: `PRIMARY`, `EXPERT`, `SECONDARY`, `INFERRED`,
`OBSERVED`. For this subject:

{{PROVENANCE_MAPPING}}

**How you read a source limits its tier.** The web tools return a summary
written by a model, not the page's own text. A claim you learned only through
a web fetch or a search result is at most `SECONDARY`, even when the page is
the specification itself. `PRIMARY` is only for text you read directly: a
local file you opened, or a passage you can copy word for word from what the
tool returned. When you are not sure the words are the source's own, use the
lower tier.

Every `PRIMARY` finding must carry a `quote` and a `source_url`: the exact
words that state the fact, and the address of the page those words are on.
For a local file, give `source_file` in place of `source_url`.

When you finish, a script opens that address itself and looks for your quote.
If the words are not there, the finding is downgraded to `SECONDARY` and the
reason is recorded on it. So quote only words you can see, and cite the page
they are actually on. A sentence from an older version of a document is not in
the current version, even if it is about the same rule.

## Verdict

End with exactly one verdict. Choose honestly; stopping is a good outcome
when there is nothing left to find.

| Verdict | Use when | You must also give |
|---|---|---|
| `exhausted` | The unknown is resolved and nothing new is worth asking | `unknowns_remaining` empty, and at least one finding |
| `irreducible` | Unknowns remain but the available sources do not hold the answer | `sources_searched`: everything you tried |
| `sufficient` | Unknowns remain but they do not matter for the goal below | `verdict_reason`: which unknowns, and why |
| `continue` | A specific further fact is findable and matters | at least one entry in `proposals` |

**The goal that decides what matters:** {{GOAL}}
**Done means:** {{DEFINITION_OF_DONE}}
**Precision needed:** {{PRECISION_BAR}}

## Proposals

Only with `continue`. Each proposal is one task for a later researcher:

    {"title": "Short title",
     "description": "What to find and why it matters",
     "unknown_being_resolved": "One concrete missing fact",
     "expected_sources": ["Where the answer is likely to be"]}

`unknown_being_resolved` must name a single fact that someone could look up,
such as "the retry backoff multiplier". "More detail on retries" will be
rejected. If you cannot name the fact and where it might be found, the right
verdict is `irreducible` or `sufficient`, not `continue`.
