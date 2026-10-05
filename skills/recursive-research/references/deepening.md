# Stage 4: recursive deepening

Produces `knowledge/tree/`. Each wave resolves specific unknowns and proposes
the next ones. Branches close on their own when they run dry.

**Web search is required** for every research wave.

## Bootstrap (wave 0)

1. `RR add-session <slug> deepening`. The first deepening session has one
   organizer task, `bootstrap`.
2. Run the task loop from `SKILL.md`. `complete-task` refuses a malformed
   tree; if it does, send the same agent the script's reason to fix, once,
   and try again before recording a failure and telling the user.
3. `RR validate <slug> proposals`. If it reports errors, have the same agent
   fix them, once.
4. Go to the gate.

## The gate

Run `RR score <slug> --apply` (after bootstrap it closes nothing). It scores
a session once; running it again only repeats the summary, so it is safe
after an interruption or a reopen. Its output is everything the gate needs.
Show the user:

- **Closed this wave:** each branch and its reason, from `closed`.
- **Still open:** from `open`.
- **Blocked:** from `blocked`, with the task errors from `RR status <slug>`.
- **Dropped:** proposals in `dropped`, each on a branch that closed. Say that
  reopening the branch brings them back.
- **Quotes:** how many `PRIMARY` findings the script downgraded this wave,
  from the `quotes_downgraded` counts that `complete-task` returned.
- **Validation:** any tree or proposal errors still left after the one fix.
- **Conflicts:** any the organizer reported, with both values and their
  sources, for the user to decide.
- **Proposals:** a numbered list from `proposals`: title, the unknown it
  resolves, where it will look, and its branch and level.
- **Cost:** approving N proposals runs N researchers, at most
  `agents_per_batch` at a time, followed by one organizer.

Tell them they can approve all, approve some, skip some, reopen a closed
branch, or stop here.

- **Reopen:** `RR reopen-branch <slug> <branch>`, then run the score command
  again to show its restored proposals. If the result has a `note`, the
  branch is at the depth cap; tell the user it will not go deeper unless they
  raise `controls.depth_cap`.
- **Record the decisions:** `RR approve-proposals <slug> --all`, or
  `RR approve-proposals <slug> <id> <id> --skip <id>`. It validates as well.
- **Nothing approved, or nothing proposed:** go to consolidation.

## A research wave

1. `RR add-session <slug> deepening`. This builds the wave from the approved
   proposals of the previous session.
2. Run the task loop from `SKILL.md`.
3. When no runnable tasks remain, `RR brief <slug> wave` and dispatch the
   organizer it names with the brief path, exactly as in the loop.
4. `RR validate <slug> tree` and `RR validate <slug> proposals`. If either
   reports errors, have the same agent fix them, once.
5. Go to the gate.

## How branches close

`score` closes a branch when any of these holds for the wave:

| Condition | Reason recorded |
|---|---|
| No researcher on the branch said `continue` | `irreducible`, `sufficient`, or `exhausted` |
| Fewer new facts than `min_new_facts` and no unknowns resolved | diminishing returns |
| Duplicate share above `max_duplicate_share` | diminishing returns |
| No unknowns resolved and weak-tier share above `max_weak_share` | diminishing returns |
| The branch reached `depth_cap` | depth cap reached |

The thresholds are in the plan under `controls.close_thresholds`. Closing is
automatic. Proposals on a closed branch are dropped, and its unresolved
unknowns are appended to `knowledge/remaining_unknowns.md`. The user can
reopen any branch at the gate.

## Consolidation

1. `RR brief <slug> consolidate` and dispatch the organizer it names. It adds
   cross-references and checks every README.
2. `RR consolidate <slug>`. The script records every unknown still open in
   `knowledge/remaining_unknowns.md` and lists lines marked `CONFLICT`.
3. `RR validate <slug> tree`.
4. `RR set-stage <slug> deepening done`.
5. `RR report <slug>` writes the whole knowledge base as one page,
   `research/<slug>/report.html`. Its output includes the headline numbers.
6. Tell the user to open that file, and give them the numbers: how many
   claims, how many verified at source, how many branches closed and why, how
   many unknowns remain, and each conflict for them to decide. For the
   per-branch figures, `RR scorecard <slug>`.
