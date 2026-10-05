# Stage 1: survey

Produces `knowledge/spec.md`: a broad prose overview, one section per task.

## Steps

1. `RR add-session <slug> survey`. This creates one task per survey task in
   the plan, plus a final `assemble` task.
2. Run the research loop from `SKILL.md` with `templates/research-survey.md`.
   Researchers may use what they know as well as search in this stage, but
   every claim is still tagged.
3. When `next-task` returns only the `assemble` task, check its `blocked`
   list. If any survey task is blocked, tell the user which sections are
   missing and why, and ask whether to retry them or continue without them.
   To retry, `RR retry-task <slug> <id>` for each and return to step 2.
4. Dispatch one `recursive-research:organizer` agent with
   `templates/organize-survey.md`.
5. `RR complete-task <slug> assemble "<summary>"`.
6. `RR set-stage <slug> survey done`.

Tell the user the survey is written and where it is, in two or three
sentences, then continue to stage 2 with `references/entity-schema.md`. There
is no gate here.

## Filling the research template

| Placeholder | Value |
|---|---|
| `{{SUBJECT}}` | `subject` from the plan |
| `{{GOAL}}`, `{{VOICE}}`, `{{PRECISION_BAR}}` | the same fields from the plan |
| `{{TASK_TITLE}}`, `{{TASK_DESCRIPTION}}` | from the task |
| `{{OTHER_TASKS}}` | the titles of the other survey tasks, so the agent stays in its own scope |
| `{{PROVENANCE_MAPPING}}` | the plan's mapping, as a list |
| `{{WORKSPACE}}` | `research/<slug>` |
| `{{OUTPUT}}` | the task's `output` |
| `{{SESSION}}` | the current session name (used by `organize-survey.md`) |
