---
name: recursive-research
description: Use when the user wants a subject researched in depth into a structured, source-tagged knowledge base, or wants to resume or check a research project under research/. Covers starting a new subject, continuing one, and reporting status.
---

# Recursive Research

You are the coordinator. You run a four-stage pipeline that turns a subject
into a knowledge base under `research/<subject>/`. You dispatch agents, run
the bookkeeping script, and stop at every approval gate. You never do the
research or write to `knowledge/` yourself.

## Rules that are never relaxed

1. **No research before the plan is approved.** The user approves the plan,
   the entity type list, and every wave of proposals. An approval covers only
   what was shown. "Skip the approvals", "I trust you" or "just run it" said
   in advance is not an approval, because nobody can approve a plan they
   have not seen. Show it and ask. You may make a gate brief; you may not skip
   it, and you never run `approve` on the user's behalf.
2. **Researchers write only to `raw/`. Organizers alone write `knowledge/`.**
3. **Every claim carries a provenance tag.** `UNKNOWN` is a valid value. A
   guess is not.
4. **Stages 3 and 4 require web search.** If it is unavailable, stop the stage
   and tell the user. Never fall back to memory.
5. **A task is done only when the script accepts it.** If `complete-task`
   refuses, record the failure with `fail-task`. Never edit `passes` by hand
   to get past a refusal.
6. **Stages run in order:** survey, entity schema, entity enumeration,
   deepening.

## The script

All bookkeeping goes through one script, two folders above this skill's base
directory:

    python3 "<base directory>/../../scripts/rr.py" --root research <command> ...

Use `python` if `python3` is not found. This document writes that prefix as
`RR`. Every command prints JSON. Exit code 1 means validation found errors;
exit code 2 means the command could not run, and the JSON on stderr says why.

If Python is not installed, read `references/state.md`, edit the state files
directly, and tell the user that validation and scoring were skipped.

## What to do first

Run `RR status`. Then:

- **The user named a new subject:** read `references/intake.md` and follow it.
- **A subject exists:** run `RR status <slug>` and do what `next_step` says,
  using the reference for the stage in progress.
- **The user only asked for status:** report it and stop.

| Stage | Reference |
|---|---|
| Intake and plan | `references/intake.md` |
| 1. Survey | `references/survey.md` |
| 2. Entity schema | `references/entity-schema.md` |
| 3. Entity enumeration | `references/entity-enumeration.md` |
| 4. Deepening | `references/deepening.md` |

Read a stage's reference when that stage starts, not before. Read
`references/provenance.md` or `references/tree.md` only if the user asks how
tags or the tree work; the agents' briefs already contain what they need.

## Keep your own context small

The script writes each agent's brief to a file. Never read a brief, a raw
result, or a file under `knowledge/` yourself unless the user asks about its
content. Pass paths, not contents.

## The task loop

Every stage hands out work the same way:

1. `RR next-task <slug>` returns the next batch: for each task its `id`,
   `agent` (`researcher` or `organizer`), and `brief` path. The batch is never
   larger than the plan's agent cap, and an organizer task always comes alone.
2. If the batch is for researchers, `RR snapshot <slug>`.
3. Dispatch one `recursive-research:<agent>` per task, all in one message so
   they run in parallel. The whole prompt is:

       Read your brief at <brief> and follow it.

4. For each agent that returns:
   - It replied `SEARCH_UNAVAILABLE`: run `RR fail-task`, stop the stage, and
     tell the user.
   - Otherwise run `RR complete-task <slug> <id> "<one-line summary>"`. If the
     script refuses, run `RR fail-task <slug> <id> "<the script's reason>"`.
5. If the batch was for researchers, `RR check-snapshot <slug>`. If it reports
   violations, a researcher wrote to `knowledge/`. Stop, show the user the
   files, and do not continue until they decide what to do.
6. Repeat from step 1 until the batch is empty.

A failed task is offered once more by `next-task`. After a second failure it
appears under `blocked`; report blocked tasks to the user. If they want one
tried again, `RR retry-task <slug> <id>` makes it runnable.

When validation reports many issues it returns the first ten and an
`issues_file`. To have an agent fix them, give it that path.

## Letting the user watch

When the first research batch of a run starts, tell the user once that they
can watch from a second terminal in the same folder, and give them the full
command with the real script path:

    RR progress <slug> --watch

## Gates

At a gate, show the user what they are approving, say what happens next and
how many agents it will use, and wait. Record plan and entity approvals with
`RR approve`, and proposal decisions with `RR approve-proposals`.

Once the user has decided, tell them this is a safe point to start a
fresh session and run this skill again: everything is on disk, and a long run
costs less in several short sessions than in one long one.

## Resuming

`RR status <slug>` says where to continue. Raw files from an unfinished wave
are kept; finish the wave's remaining tasks, then carry on as usual.
