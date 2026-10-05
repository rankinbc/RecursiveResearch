# Stage 3: entity enumeration

Produces `knowledge/entities/<type_id>.json` for each entity type: every
instance, with a provenance tier on every value.

**Web search is required.** Researchers in this stage must not rely on what
they remember. Earlier testing showed that agents without search fabricate
values and mix up different versions of a subject.

## Steps

1. `RR add-session <slug> entity_enumeration`. This creates one task per
   approved entity type. The task id is the type's file id.
2. Run the task loop from `SKILL.md`, with this order once a batch of agents
   has returned:
   1. `RR check-snapshot <slug>` first. Promotion writes to `knowledge/`, so
      the check must run before it. Stop on violations as usual.
   2. For each agent, `RR promote-entity <slug> <id>`. It validates the
      roster and copies it into `knowledge/entities/`.
   3. If it reports errors, tell the same agent to fix the issues in the
      `issues_file` it returned (or the listed issues if there is no file),
      once, then promote again.
   4. If it succeeds, `RR complete-task <slug> <id> "<count> instances"`.
      If it still fails, `RR fail-task <slug> <id> "<errors> errors remain"`.
3. If any type is blocked, tell the user which and why, and ask whether to
   retry or continue without it. To retry, `RR retry-task <slug> <id>` and
   return to step 2.
4. `RR set-stage <slug> entity_enumeration done`.

Tell the user which types were enumerated and which, if any, were left out,
then continue to stage 4 with `references/deepening.md`. There is no gate
here.
