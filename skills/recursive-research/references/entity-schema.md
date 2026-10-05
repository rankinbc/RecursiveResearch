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
`knowledge/entities.json` to match, then validate again. This is the one file
under `knowledge/` you edit yourself, and only to record what the user
decided at this gate: it is their list, not a research finding. When they
approve:

    RR approve <slug> entity_types

The approval covers the list as it was shown. If the file changes afterwards,
stage 3 will not start until you show the user the list and approve again.

Then start stage 3 with `references/entity-enumeration.md`.
