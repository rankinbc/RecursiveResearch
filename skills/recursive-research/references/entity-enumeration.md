# Stage 3: entity enumeration

Produces `knowledge/entities/<type_id>.json` for each entity type: every
instance, with a provenance tier on every value.

**Web search is required.** Researchers in this stage must not rely on what
they remember. Earlier testing showed that agents without search fabricate
values and mix up different versions of a subject.

## Steps

1. `RR add-session <slug> entity_enumeration`. This creates one task per
   approved entity type. The task id is the type's file id.
2. Run the research loop from `SKILL.md` with `templates/research-entity.md`,
   with one change to step 4. For each agent that returns:
   - Run `RR promote-entity <slug> <id>`. It validates the roster and copies
     it into `knowledge/entities/`.
   - If it reports errors, send the errors back to the same agent to fix,
     once, then run it again.
   - If it succeeds, `RR complete-task <slug> <id> "<count> instances"`.
   - If it still fails, `RR fail-task <slug> <id> "<the errors>"`.

   Take the knowledge snapshot after the promotions of one batch and before
   dispatching the next, so promotions are not reported as violations.
3. If any type is blocked, tell the user which and ask whether to retry or
   continue without it.
4. `RR set-stage <slug> entity_enumeration done`.

Tell the user how many instances each type has and how many values are
`UNKNOWN`, then continue to stage 4 with `references/deepening.md`. There is
no gate here.

## Filling the research template

| Placeholder | Value |
|---|---|
| `{{SUBJECT}}` | `subject` from the plan |
| `{{TYPE_NAME}}` | the entity type's name |
| `{{TYPE_SCHEMA}}` | that type's entry from `knowledge/entities.json`, as JSON |
| `{{PROVENANCE_MAPPING}}` | the plan's mapping, as a list |
| `{{WORKSPACE}}` | `research/<slug>` |
| `{{OUTPUT}}` | the task's `output` |
