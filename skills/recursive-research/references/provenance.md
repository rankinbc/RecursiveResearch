# Provenance

Every factual claim in the knowledge base carries exactly one tier.

| Tier | Meaning |
|---|---|
| `PRIMARY` | The thing itself: source code, the binary, the original document, raw data |
| `EXPERT` | Verified by practitioners with direct access |
| `SECONDARY` | Published guides, references, wikis |
| `INFERRED` | Derived from other tagged facts |
| `OBSERVED` | Seen but not confirmed |
| `UNKNOWN` | Needed but not found |

Conflicts are resolved by precedence, strongest first:

    PRIMARY > EXPERT > SECONDARY > INFERRED > OBSERVED

## Choosing a tier

The plan's `provenance_mapping` lists the concrete sources that count as
`PRIMARY`, `EXPERT`, and `SECONDARY` for this subject. Find the source in the
mapping and use its tier. If a source is not in the mapping, use the tier of
the most similar source that is, and name the source exactly.

- `INFERRED` is for a conclusion you derived. Say what it was derived from.
- `OBSERVED` is for something seen once or reported without confirmation.
- Something you remember but found no source for in this session is not a
  finding. In stage 1 it may be written as `OBSERVED`. In stages 3 and 4 it
  must be recorded as `UNKNOWN`.

## How you read a source limits its tier

The mapping gives the tier a source deserves when it is read directly. The
web tools do not do that: they return a summary written by a model, not the
page's own text. So a claim learned only through a web fetch or a search
result is at most `SECONDARY`, even when the page is the primary source.

`PRIMARY` is only for text read directly: a local file, or a passage copied
word for word.

In stage 4 this is checked. Every `PRIMARY` finding carries the passage as a
`quote` with a `source_url` or `source_file`. When the task completes, the
script opens that source itself and looks for the quote. If it is there the
finding is marked `"verified": true`. If not, the finding is downgraded to
`SECONDARY` and the reason is recorded in `verify_note`. A source the script
cannot open, such as a `gemini://` address or a page that fails to load,
counts as not confirmed.

The survey and the entity rosters are not checked this way. There the cap is
an instruction to the researcher, so treat their `PRIMARY` tags with more
caution than a verified stage 4 finding.

## Writing tags

In Markdown, put the tag after the claim:

    The header is 12 bytes [PRIMARY]. Retries are capped at about five [OBSERVED].
    The backoff multiplier is not documented [UNKNOWN: est 1.5-2].

An unknown may carry an estimated range after a colon.

In a JSON leaf file, put the tier and source in `_meta`:

    {
      "_meta": {
        "provenance": "PRIMARY",
        "source": "RFC 9999, section 4.2",
        "last_updated": "2026-10-04"
      },
      "max_frame_bytes": 16384
    }

`_meta.provenance` is the tier of the weakest value in the file. If the file
mixes tiers, split it or add a per-field `provenance` object.

In an entity roster, each entity has a `provenance` field: one tier for the
whole entity, or an object giving a tier for each property. A property whose
value is `null` must be `UNKNOWN`.
