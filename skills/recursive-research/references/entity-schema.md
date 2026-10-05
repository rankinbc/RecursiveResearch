# Stage 2: entity schema

Produces `knowledge/entities.json`: which kinds of thing exist and what
properties they have. This is a schema pass. It does not list every instance.

## Steps

1. `RR add-session <slug> entity_schema`. This creates one task, `schema`.
2. Dispatch one `recursive-research:organizer` agent with
   `templates/organize-schema.md`. Fill `{{SUBJECT}}`, `{{WORKSPACE}}`, and
   `{{EXPECTED_TYPES}}` (the plan's `entity_types`).
3. `RR validate <slug> entity_schema`. If it reports errors, send them back to
   the same agent to fix, once. If it still fails, `RR fail-task` and tell the
   user.
4. `RR complete-task <slug> schema "<N> entity types"`.
5. `RR set-stage <slug> entity_schema done`.

## Gate: the entity type list

Show the user a table: each type, its description, its estimated count, and
its properties. Say that stage 3 will run one researcher per type, with web
search, at most the agent cap at a time.

They may remove types, add types, or change properties. Edit
`knowledge/entities.json` to match, then validate again. When they approve:

    RR approve <slug> entity_types

Then start stage 3 with `references/entity-enumeration.md`.
