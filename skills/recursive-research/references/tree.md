# The knowledge tree

`knowledge/tree/` is a hierarchy in which each level adds detail. The deeper
you go, the more precise the content.

    knowledge/tree/
      README.md               # the subject, how it works end to end, index of branches
      <branch>/
        README.md             # how this part works, and links deeper
        <sub-branch>/
          README.md           # detailed behaviour
          frame_sizes.json    # leaf: exact values
          retry_algorithm.md  # leaf: a formula or algorithm

Depth varies by branch. A simple branch may be two levels; a complex one may
be five. Let the content decide.

A **branch** is a folder path relative to `knowledge/tree/`, such as `wire` or
`wire/framing`. Each branch opens and closes on its own: closing `wire` does
not close `wire/framing`, because the parent's own questions can run dry while
a sub-topic still has findable ones. A proposal belongs to exactly one branch,
the folder its output goes in.

## Every folder has a README.md

It must:

1. Summarize what this level covers in one to three paragraphs.
2. State the key facts at this level of detail, each tagged.
3. Link to each deeper file and folder with a one-line description.
4. End with a `## Known Unknowns` section: a checklist of specific facts that
   are still missing. Write `- none` if there are none.

Each unknown must be one concrete missing fact:

    ## Known Unknowns
    - [ ] The maximum frame length in bytes
    - [ ] Whether the retry timer resets after a partial response

Not "more detail on framing".

## Leaf files

Leaves hold exact content, not summaries.

- **JSON** for tables: values, lists, lookup tables. Must have a `_meta`
  object with `provenance` and `source`.
- **Markdown** for formulas and algorithms. Include a prose explanation,
  pseudocode, and a worked example with real values. Tag every number.

Name files after what they hold, in snake_case: `retry_algorithm.md`,
`frame_sizes.json`. Never `data.json` or `notes.md`.

## Reference, do not duplicate

If `knowledge/entities/<type>.json` already holds the data, link to it. If two
branches need the same fact, it lives in one and the other links to it.
