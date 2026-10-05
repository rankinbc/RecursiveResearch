# Stage 1: survey

Produces `knowledge/spec.md`: a broad prose overview, one section per task.

## Steps

1. `RR add-session <slug> survey`. This creates one task per survey task in
   the plan, plus a final `assemble` task for the organizer.
2. Run the task loop from `SKILL.md`. Researchers may use what they know as
   well as search in this stage, but every claim is still tagged.
3. When `next-task` returns only the `assemble` task, check its `blocked`
   list. If any survey task is blocked, tell the user which sections are
   missing and why, and ask whether to retry them or continue without them.
   To retry, `RR retry-task <slug> <id>` for each and return to step 2.
4. `RR assemble-survey <slug>`. The script joins the sections in order and
   writes the contents list, so no agent has to retype the survey.
5. Dispatch the organizer for the `assemble` task as the loop describes. It
   reviews the assembled file and edits it in place.
6. `RR complete-task <slug> assemble "<summary>"`.
7. `RR set-stage <slug> survey done`.

Tell the user the survey is written and where it is, in two or three
sentences, then continue to stage 2 with `references/entity-schema.md`. There
is no gate here.
