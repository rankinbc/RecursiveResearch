# Build the knowledge tree for {{SUBJECT}}

Build `{{WORKSPACE}}/knowledge/tree/` from what is already known, then write
the first research proposals.

Read:

- `{{WORKSPACE}}/knowledge/spec.md`
- `{{WORKSPACE}}/knowledge/entities.json`, for which entity types exist
- the file names in `{{WORKSPACE}}/knowledge/entities/`.
  Do not open the roster files: the tree links to them and never copies
  their data.

**The goal:** {{GOAL}}
**Precision needed:** {{PRECISION_BAR}}

## 1. Build the tree

Create one folder per major system, component, or theme. Let the subject
decide the branches; do not copy the survey's section list. Two levels is
enough for now.

Every folder gets a `README.md` that:

1. Summarizes what the folder covers in one to three paragraphs.
2. States the key facts already known, each with its provenance tag carried
   over from the survey.
3. Links to deeper folders and to entity files such as
   `../../entities/message_type.json`. Do not copy entity data into the tree.
4. Ends with `## Known Unknowns`: a checklist of specific missing facts that
   the goal needs. Write `- none` if there are none.

Also write `{{WORKSPACE}}/knowledge/tree/README.md`: what the subject is, how
it works end to end, an index of the branches, and its own `## Known
Unknowns`.

A JSON leaf must have exactly this `_meta` block, with both fields filled in:

    {
      "_meta": {
        "provenance": "SECONDARY",
        "source": "Where the values came from: a document and section, or a web address",
        "last_updated": "YYYY-MM-DD"
      },
      "max_frame_bytes": 16384
    }

`_meta.provenance` is the weakest tier among the values in the file. If the
values have different tiers, also give each entry its own `tier`.

Each unknown is one concrete fact someone could look up, such as "the
maximum frame length in bytes". Not "more detail on framing".

## 2. Write proposals

Write `{{WORKSPACE}}/sessions/{{SESSION}}/proposals/level_1.json`:

    {"level": 1, "proposals": [{
      "id": "framing-max-length",
      "title": "Find the maximum frame length",
      "description": "What to find and why the goal needs it",
      "branch": "wire/framing",
      "target_file": "knowledge/tree/wire/framing/frame_sizes.json",
      "unknown_being_resolved": "The maximum frame length in bytes",
      "expected_sources": ["RFC 9999, section 4"],
      "level": 1,
      "status": "proposed"
    }]}

- One proposal per unknown that matters for the goal. Leave out unknowns the
  goal does not need.
- `id` uses lowercase letters, digits, and hyphens, and is unique.
- `branch` is the folder path under `knowledge/tree/`. `target_file` must be
  inside that folder.
- Give every proposal a different scope. Two proposals must never chase the
  same fact.

## 3. Write the coordination brief

Write `{{WORKSPACE}}/sessions/{{SESSION}}/coordination_brief.md`: for each
proposal id, one line saying what it owns and which neighbouring proposal
owns the things it might be tempted to cover.
