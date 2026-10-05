# Stage 2: entity schema

Produces `knowledge/entities.json`: which kinds of thing exist and what
properties they have. This is a schema pass. It does not list every instance.

## Steps

1. `RR add-session <slug> entity_schema`. This creates one organizer task,
   `schema`.
2. Run the task loop from `SKILL.md`. `complete-task` refuses an invalid
   schema; if it does, send the same agent the script's reason to fix, once,
   and try again before recording a failure.
3. `RR set-stage <slug> entity_schema done`.

## Gate: the entity type list

Run `RR validate <slug> entity_schema`, then read `knowledge/entities.json`
(this is one of the few files you read, because the user must approve it).
Show the user a table: each type, its description, its estimated count, and
its properties. Say that stage 3 will run one researcher per type, with web
search, at most the agent cap at a time.

They may remove types, add types, or change properties. Edit
`knowledge/entities.json` to match, then validate again. When they approve:

    RR approve <slug> entity_types

Then start stage 3 with `references/entity-enumeration.md`.
