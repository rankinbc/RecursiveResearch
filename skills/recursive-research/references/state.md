# State files

Read this only when Python is unavailable and you must edit state by hand, or
when you need to explain a file to the user.

## Layout

    research/<slug>/
      plan.json
      knowledge/
        spec.md
        entities.json
        entities/<type_id>.json
        tree/
        remaining_unknowns.md
      sessions/<session>/
        tasks.json
        activity.md
        raw/
        proposals/level_<N>.json
        ledger.json              # deepening waves only
        knowledge_snapshot.json

Session names are `<date>_<stage>`, or `<date>_deepening_w<NN>` for deepening.
Wave `w00` is the bootstrap. `plan.json` lists sessions in order under
`sessions`; the last one is current.

## plan.json

Besides the fields intake fills in:

- `approvals`: `{"plan": bool, "entity_types": bool}`
- `stages`: each of `survey`, `entity_schema`, `entity_enumeration`,
  `deepening` is `pending`, `in_progress`, or `done`
- `branches`: `{"<branch>": {"status": "open" | "closed", "level": N,
  "reason": "...", "session": "..."}}`

## tasks.json

    {"session": "...", "stage": "...", "tasks": [ ... ]}

Each task has `id`, `title`, `description`, `output` (path relative to the
workspace), `solo`, `passes`, `attempts`, `last_error`, `verdict`, and for
deepening tasks `branch`, `level`, `target`, `unknown`, `expected_sources`.

- A task is done when `passes` is true. Only set it after confirming the
  `output` file exists and is not empty.
- A failed attempt adds 1 to `attempts` and sets `last_error`. At 2 attempts
  the task is blocked.
- A `solo` task runs alone, after every task before it is done or blocked.

Append one line to `activity.md` for every completion or failure.

## proposals/level_N.json

    {"level": N, "proposals": [{
      "id": "...", "title": "...", "description": "...",
      "branch": "wire/framing",
      "target_file": "knowledge/tree/wire/framing/frame_sizes.json",
      "unknown_being_resolved": "The maximum frame length in bytes",
      "expected_sources": ["RFC 9999, section 4"],
      "level": N,
      "status": "proposed"
    }]}

`status` is `proposed`, `approved`, `skipped`, or `dropped`.

## ledger.json

    {"entries": [{"task_id": "...", "finding": 0,
                  "disposition": "new" | "duplicate" | "conflict",
                  "placed_in": "knowledge/tree/..."}]}

One entry for every finding in every completed task of the wave.

## Without the script

Apply the closing rules in `references/deepening.md` by counting from the raw
files and the ledger yourself, and tell the user the counts were done by hand.
