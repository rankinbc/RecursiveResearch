# Stage 4: recursive deepening

Produces `knowledge/tree/`. Each wave resolves specific unknowns and proposes
the next ones. Branches close on their own when they run dry.

**Web search is required** for every research wave.

## Bootstrap (wave 0)

1. `RR add-session <slug> deepening`. The first deepening session has one
   task, `bootstrap`.
2. Dispatch one `recursive-research:organizer` agent with
   `templates/organize-bootstrap.md`.
3. `RR validate <slug> tree` and `RR validate <slug> proposals`. Send errors
   back to the same agent to fix, once.
4. `RR complete-task <slug> bootstrap "<summary>"`.
5. Go to the gate.

## The gate

Run `RR score <slug> --apply` (after bootstrap it closes nothing and only
counts proposals). Then show the user:

- **Closed this wave:** each branch and its reason, from `closed`.
- **Still open:** from `open`.
- **Blocked:** branches whose tasks all failed, with the errors.
- **Conflicts:** any lines the organizer marked `CONFLICT`, with both values
  and their sources, for the user to decide.
- **Proposals:** a numbered list from the session's `proposals/` files with
  status `proposed`: title, the unknown it resolves, where it will look, and
  its branch and level.
- **Cost:** approving N proposals runs N researchers, at most
  `agents_per_batch` at a time, followed by one organizer.

Tell them they can approve all, approve some, skip some, edit any, reopen a
closed branch, or stop here.

- **Reopen:** `RR reopen-branch <slug> <branch>`, then show its restored
  proposals. If the result has a `note`, the branch is at the depth cap; tell
  the user it will not go deeper unless they raise `controls.depth_cap`.
- **Approve or skip:** set each proposal's `status` to `approved` or
  `skipped` in the proposals file. Then `RR validate <slug> proposals`.
- **Nothing approved, or nothing proposed:** go to consolidation.

## A research wave

1. `RR add-session <slug> deepening`. This builds the wave from the approved
   proposals of the previous session.
2. Run the research loop from `SKILL.md` with
   `templates/research-deepening.md`.
3. When no runnable tasks remain, dispatch one `recursive-research:organizer`
   agent with `templates/organize-wave.md`.
4. `RR validate <slug> tree` and `RR validate <slug> proposals`. Send errors
   back to the same agent to fix, once.
5. Go to the gate.

## How branches close

`score` closes a branch when any of these holds for the wave:

| Condition | Reason recorded |
|---|---|
| No researcher on the branch said `continue` | `irreducible`, `sufficient`, or `exhausted` |
| Fewer new facts than `min_new_facts` | diminishing returns |
| Duplicate share above `max_duplicate_share` | diminishing returns |
| No unknowns resolved and weak-tier share above `max_weak_share` | diminishing returns |
| The branch reached `depth_cap` | depth cap reached |

The thresholds are in the plan under `controls.close_thresholds`. Closing is
automatic. Proposals on a closed branch are dropped, and its unresolved
unknowns are appended to `knowledge/remaining_unknowns.md`. The user can
reopen any branch at the gate.

## Consolidation

1. Dispatch one `recursive-research:organizer` agent with
   `templates/organize-consolidate.md`.
2. `RR validate <slug> tree`.
3. `RR set-stage <slug> deepening done`.
4. Tell the user where the knowledge base is, how many branches closed and
   why, and how many unknowns remain in `remaining_unknowns.md`.

## Filling the templates

| Placeholder | Value |
|---|---|
| `{{SUBJECT}}`, `{{GOAL}}`, `{{PRECISION_BAR}}`, `{{DEFINITION_OF_DONE}}` | from the plan |
| `{{PROVENANCE_MAPPING}}` | the plan's mapping, as a list |
| `{{WORKSPACE}}` | `research/<slug>` |
| `{{SESSION}}` | the current session name |
| `{{TASK_ID}}`, `{{TASK_TITLE}}`, `{{TASK_DESCRIPTION}}` | from the task |
| `{{UNKNOWN}}`, `{{EXPECTED_SOURCES}}`, `{{BRANCH}}`, `{{TARGET}}`, `{{OUTPUT}}` | from the task |
| `{{BRIEF}}` | the contents of the previous session's `coordination_brief.md` |
| `{{NEXT_LEVEL}}` | the wave's level plus 1 |
| `{{DEPTH_CAP}}` | `controls.depth_cap` |
| `{{CLOSED_BRANCHES}}` | the closed branches from `RR status` |
