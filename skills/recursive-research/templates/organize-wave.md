# Organize research wave {{SESSION}} for {{SUBJECT}}

Researchers wrote results into `{{WORKSPACE}}/sessions/{{SESSION}}/raw/`, one
JSON file per task. Place the findings in `{{WORKSPACE}}/knowledge/tree/`,
record what you did with each one, and write the next proposals.

Read `{{WORKSPACE}}/sessions/{{SESSION}}/tasks.json`. Process only tasks whose
`passes` is true. Each task names its `branch` and `target` file.

## 1. Place every finding

For each finding in each raw file, decide one disposition:

- **new**: the tree does not have this fact. Write it into the task's target
  file, or a better-fitting file in the same branch. Keep its tier and source.
- **duplicate**: the tree or an entity file already has this fact at an equal
  or stronger tier. Do not write it again.
- **conflict**: the tree has a different value for the same fact. The
  stronger tier wins (`PRIMARY > EXPERT > SECONDARY > INFERRED > OBSERVED`).
  If the new finding is stronger, replace the old value. At the same tier,
  keep both with their sources and mark the line `CONFLICT`.

Follow the tree conventions: a `README.md` in every folder ending with
`## Known Unknowns`; JSON leaves with `_meta.provenance` and `_meta.source`;
Markdown leaves with tagged claims; file names that say what the file holds.

A fact that fits two branches lives in one, and the other links to it.

## 2. Write the ledger

Write `{{WORKSPACE}}/sessions/{{SESSION}}/ledger.json` with one entry for
every finding of every completed task, in order:

    {"entries": [
      {"task_id": "framing-max-length", "finding": 0, "disposition": "new",
       "placed_in": "knowledge/tree/wire/framing/frame_sizes.json"}
    ]}

`finding` is the finding's position in the raw file, starting at 0. For a
duplicate, `placed_in` is where the existing copy is. Be strict: a fact
restated in different words is still a duplicate. These counts decide which
branches close.

## 3. Update Known Unknowns

In each README you touched: tick off unknowns listed in the raw files'
`unknowns_resolved`, and add those in `unknowns_remaining` that are not
already there.

## 4. Write the next proposals

Collect the `proposals` from raw files whose verdict is `continue`. Then
write `{{WORKSPACE}}/sessions/{{SESSION}}/proposals/level_{{NEXT_LEVEL}}.json`:

    {"level": {{NEXT_LEVEL}}, "proposals": [{
      "id": "...", "title": "...", "description": "...",
      "branch": "wire/framing",
      "target_file": "knowledge/tree/wire/framing/extension_frames.md",
      "unknown_being_resolved": "One concrete missing fact",
      "expected_sources": ["..."],
      "level": {{NEXT_LEVEL}},
      "status": "proposed"
    }]}

- Merge proposals that chase the same fact. Each remaining proposal owns a
  scope no other proposal touches.
- Add a proposal for any gap that falls between branches and that no
  researcher owned. Assign it to the most relevant branch.
- Drop a proposal whose unknown is not one concrete fact, or that the goal
  does not need.
- Do not write proposals for these closed branches: {{CLOSED_BRANCHES}}
- Do not write any proposals if {{NEXT_LEVEL}} is greater than the depth cap
  of {{DEPTH_CAP}}. Write the file with an empty list.
- `id` uses lowercase letters, digits, and hyphens, and is unique.
  `target_file` must be inside `knowledge/tree/<branch>/`.

**The goal:** {{GOAL}}

## 5. Write the coordination brief

Write `{{WORKSPACE}}/sessions/{{SESSION}}/coordination_brief.md`: for each
proposal id, one line saying what it owns and which neighbouring proposal
owns the things it might be tempted to cover.
