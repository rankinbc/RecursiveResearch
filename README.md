# RecursiveResearch

A Claude Code plugin that researches a subject to a chosen depth and leaves
behind a structured, source-tagged knowledge base. The research writes its own
next-level backlog from the gaps it finds, and stops each branch when it runs
dry.

## Requirements

- Claude Code with web search available
- Python 3.9 or later on your PATH

## Install

Load it for one session:

    claude --plugin-dir /path/to/RecursiveResearch

## Use

In any project folder:

    /recursive-research:recursive-research

Name a subject to start, or run it again later to resume. It works in four
stages and asks for your approval three times:

| Stage | What it produces | Your approval |
|---|---|---|
| Intake | `research/<subject>/plan.json` | The plan |
| 1. Survey | `knowledge/spec.md` | |
| 2. Entity schema | `knowledge/entities.json` | The entity type list |
| 3. Entity enumeration | `knowledge/entities/<type>.json` | |
| 4. Deepening | `knowledge/tree/` and `knowledge/remaining_unknowns.md` | Each wave of proposals |

Every claim carries a provenance tier: `PRIMARY`, `EXPERT`, `SECONDARY`,
`INFERRED`, `OBSERVED`, or `UNKNOWN`.

## Watching a run

From a second terminal in the same project folder:

    python /path/to/RecursiveResearch/scripts/rr.py --root research progress <subject> --watch

It refreshes every 5 seconds and shows task counts per stage, which tasks are
running, done or blocked, findings per wave, and which branches are open or
closed and why. A task shows as running from when it is handed to an agent
until it completes or fails; there is no view inside an agent while it works.

## Controlling cost and depth

Set these in `plan.json` under `controls`, or ask for them at the plan gate:

| Setting | Default | Meaning |
|---|---|---|
| `depth_cap` | 4 | No branch goes deeper than this many waves |
| `max_agents_per_wave` | 4 | Agents running at once |
| `close_thresholds` | 3 / 0.6 / 0.8 | When a branch is closed for diminishing returns |

A branch closes on its own when:

- its researchers report nothing left to find, or nothing findable, or
  nothing that matters for your goal;
- a wave added fewer than 3 new facts and resolved no unknowns;
- more than 60% of a wave's findings were duplicates;
- a wave resolved nothing and more than 80% of its findings were inferred or
  observed;
- it reaches the depth cap.

Each gate lists what closed and why, and you can reopen any branch.

## Status

The bookkeeping script and the plugin files are implemented and unit-tested.
The plugin has not yet been run end to end on a real subject, and its prompts
have not been pressure-tested; see Tasks 4 and 5 in
`docs/plans/2026-10-05-skill-layer.md`.

## Development

    python -m unittest discover -s tests

Design: `docs/specs/2026-10-04-recursive-research-design.md`.
