# RecursiveResearch -- Design

Date: 2026-10-04
Status: implemented, with the changes listed below

## Changes since this design

The design below is as originally agreed. Building and running it changed
these points. Where a section below disagrees with this list, the list is
right.

- **One script, not several.** All bookkeeping is `scripts/rr.py` with
  subcommands. Beyond those in "State and scripts" it has `approve`,
  `retry-task`, `set-stage`, `promote-entity`, `snapshot`, `check-snapshot`,
  `reopen-branch`, `brief`, `assemble-survey`, `approve-proposals`,
  `consolidate`, and `progress`.
- **Briefs are rendered by the script.** The coordinator passes each agent
  the path of its filled-in brief and never fills a template by hand.
- **Entity rosters go through `raw/`.** A researcher writes its roster to
  `raw/`; the script validates it and copies it into `knowledge/entities/`.
- **The survey is assembled by the script.** The organizer reviews
  `spec.md` and edits it in place.
- **The script closes branches.** The organizer records each finding as new,
  duplicate, or conflict in a ledger; the script counts and applies the
  thresholds. A session is scored once, so repeating the step is safe.
- **Branches close one at a time.** Closing a branch does not close its
  sub-branches.
- **The "few new facts" rule also needs no unknowns resolved.** Each task
  resolves one unknown, so a low count alone does not mean a dry branch.
- **A `continue` verdict needs a proposal** naming a concrete unknown.
- **Depth is the wave level.** A proposal's level is its parent task's level
  plus one.
- **Researcher writes to `knowledge/` are detected, not prevented.** Tool
  access cannot restrict a path, so the script compares `knowledge/` before
  and after each research batch.
- **How a source was read caps its tier.** Web tools return a model's summary,
  so anything learned only that way is at most `SECONDARY`, and a `PRIMARY`
  finding in stage 4 must carry the exact quote.
- **Remembered claims in the survey are `OBSERVED`.** In stages 3 and 4 they
  must be `UNKNOWN`.
- **Rules are enforced in the script:** no research before the plan is
  approved, stages in order, and no task marked done without valid output.

## Purpose

RecursiveResearch is a Claude Code plugin that researches an arbitrary subject
to a chosen depth and leaves behind a structured, source-tagged knowledge base.

It generalises the game research method developed in the GameAnalysis2
repository. That method is a pipeline in which each stage turns the previous
stage's output into something more structured and more precise, and in which
the research writes its own next-level backlog from the gaps it finds. Almost
none of that machinery is specific to games. This plugin keeps the machinery
and replaces the game-specific layer with a plan generated for each subject.

The plugin is intended to be shared with other people. It must be
self-contained and must not depend on ClaudeContainer, Docker, or any package
outside the Python standard library.

## Decisions

| Question | Decision |
|---|---|
| Audience | A shareable plugin, usable by people other than the author |
| Source of domain knowledge | Generated at intake for each subject, approved by the user |
| Execution | In-session: a coordinator skill dispatches subagents; all state on disk |
| Pipeline | Four mandatory stages, in the order proven in GameAnalysis2 |
| Bookkeeping | Bundled Python scripts, standard library only |
| Provenance | Fixed universal tiers; concrete sources mapped to tiers per subject |
| Stopping | Per-branch verdicts and scoring; dry branches close automatically |

Names: the repository is `RecursiveResearch`; the plugin and its skill are
`recursive-research`.

## Plugin layout

```
RecursiveResearch/
  .claude-plugin/plugin.json
  skills/recursive-research/
    SKILL.md              # coordinator: intake, stage routing, approval gates
    references/           # one doc per stage, plus provenance and tree conventions
    templates/            # agent prompts with {{PLACEHOLDER}} fields
    examples/games/       # the GameAnalysis2 21-task template, as a worked example
  agents/
    researcher.md         # web search and read; writes only to the raw area
    organizer.md          # reads raw output; the only role that writes the tree
  scripts/                # scaffold, next_task, complete_task, status, validate, score
  tests/
  docs/specs/
```

There is one user-facing skill, `/recursive-research`. It reads the state on
disk and decides what to do: start a new subject, resume at the next
incomplete task, or report status.

`SKILL.md` stays short. It loads a stage's reference doc only when that stage
runs.

The researcher and organizer are plugin agents so that the split between them
is enforced by tool access and not only by instructions.

## Workspace layout

The plugin creates this in the user's project:

```
research/<subject>/
  plan.json               # subject, goal, voice, entity types, provenance mapping,
                          # definition of done, controls, stage status
  knowledge/
    spec.md               # stage 1: prose survey
    entities.json         # stage 2: entity types and schemas
    entities/<type>.json  # stage 3: full rosters
    tree/                 # stage 4: hierarchy; README plus Known Unknowns per folder
    remaining_unknowns.md # what was not found, and why
  sessions/<date>_<stage>/
    tasks.json            # task list with passes true/false
    activity.md           # append-only log, one line per completed task
    raw/                  # researcher output, before organizing
    proposals/            # next-level tasks awaiting approval
```

`<subject>` is a short slug. The plan is JSON so the scripts need no
third-party parser.

## Intake

The skill asks a small number of questions, one at a time:

- what the subject is
- what the research is for
- how deep and how precise it needs to be
- what sources or local material the user already has

It then drafts `plan.json` containing:

- **Survey task list.** A fixed universal set (overview, how it works end to
  end, history and context, comparison with peers, final review) plus tasks
  specific to the subject.
- **Voice and precision bar.** How findings should be written, and what counts
  as specific enough.
- **Expected entity types.** Every subject gets an entity pass, so intake
  names the types it expects (for a protocol: message types, states, error
  codes).
- **Provenance mapping.** Which concrete sources count as which tier.
- **Definition of done.** What the user needs to be able to do with the result.
- **Controls.** Depth cap per branch and maximum agents per wave.

The user edits and approves the plan before any research runs.

## Provenance

Every claim in the knowledge base carries one tag. The tiers and their order
are fixed:

| Tier | Meaning |
|---|---|
| `PRIMARY` | The thing itself: source code, the binary, the original document, raw data |
| `EXPERT` | Verified by practitioners with direct access |
| `SECONDARY` | Published guides, references, wikis |
| `INFERRED` | Derived from other tagged facts |
| `OBSERVED` | Seen but not confirmed |
| `UNKNOWN` | Needed but not found; may carry an estimated range |

Conflicts are resolved by precedence:
`PRIMARY > EXPERT > SECONDARY > INFERRED > OBSERVED`.

The plan maps concrete sources to tiers for the subject. Agents apply the
mapping; they do not decide tiers themselves.

In Markdown, tags follow the claim inline. In JSON, they go in a `_meta`
object or per field, with the specific source and the date.

Two rules are absolute:

- Every factual claim is tagged. `UNKNOWN` is a valid value; a guess is not.
- Stages 3 and 4 use agents with web search. They never rely on training
  knowledge alone.

## Stages

### Stage 1: survey

- The coordinator dispatches one researcher per task from the approved list.
  Independent tasks run in parallel, limited by the per-wave agent cap.
- Each researcher writes its section to `raw/`.
- An organizer assembles `knowledge/spec.md` in task order, so parallel agents
  never write to the same file.
- The final review task (table of contents, cross-references, fixing
  inconsistencies) runs last, on its own.

### Stage 2: entity schema

- One agent reads `spec.md` and writes `knowledge/entities.json`: each entity
  type, its properties, a rough instance count, its relationships, and two or
  three examples.
- This is a schema pass, not a completeness pass.
- **Gate:** the user approves or edits the type list, because stage 3 spends
  one agent per type.

### Stage 3: entity enumeration

- One researcher per entity type produces `knowledge/entities/<type>.json`
  with every instance and a provenance tag on each value.
- The validation script checks each file against its schema and flags
  untagged values.

### Stage 4: recursive deepening

1. **Bootstrap (level 0).** An organizer builds `knowledge/tree/` from the
   spec and entities. Each folder gets a README that summarises the level,
   links deeper, and ends with `Known Unknowns`. The first proposals are
   generated from those unknowns.
2. **Gate.** The user approves, edits, or skips proposals.
3. **Research wave.** One researcher per approved task. Each receives the
   coordination brief and writes only to `raw/`, ending with a verdict.
4. **Organizer wave.** Places findings into the tree, removes duplicates,
   resolves conflicts, scores each branch, closes dry branches, and writes the
   next coordination brief and proposals.
5. Repeat from step 2 until every branch is closed, the depth cap is reached,
   or the user stops.
6. **Consolidation.** A cross-reference pass, then `remaining_unknowns.md`.

The tree references entity files where they already hold the data; it does not
copy them.

## Roles

**Researcher.** Finds and extracts data for one task. Writes only to the
session's `raw/` area. Does not touch `knowledge/` and does not decide where
data belongs.

**Organizer.** Runs after each research wave and is the only role that writes
to `knowledge/`. It must:

1. Place raw findings in the correct location.
2. Remove duplicates: keep one canonical copy and make other locations
   reference it.
3. Resolve conflicting values by tier precedence.
4. Find gaps that fall between branches and assign each to one owner.
5. Score each branch and recommend closing or continuing.
6. Write the coordination brief for the next wave: what each researcher owns,
   what others own, and where the cross-references are.

**Coordinator.** The skill itself. It dispatches agents, calls the scripts,
presents gates, and never does research.

## Stopping

Depth is a cap per branch, not a target. Each branch closes on its own as soon
as it runs dry.

### Researcher verdicts

Every stage 4 research task ends with one verdict:

| Verdict | Meaning | Required evidence |
|---|---|---|
| `exhausted` | Every assigned unknown is resolved and nothing new is worth asking | None beyond the findings |
| `irreducible` | Unknowns remain but the available sources do not contain the answer | The list of sources searched |
| `sufficient` | Unknowns remain but are below the precision the plan's goal requires | Which unknowns, and why they do not matter |
| `continue` | Proposes sub-tasks | Each proposal names the specific unknown and where to look |

### Proposal validation

A proposal must name a concrete unknown, a target file, and expected sources.
The validation script rejects any proposal that does not. "Research this topic
further" is not a valid proposal.

### Branch scoring

The organizer checks researcher verdicts against counts the scripts produce
for each branch in the wave:

- new tagged facts added
- unknowns resolved against unknowns opened
- the share of findings that duplicate what the tree already holds
- the share that is only `INFERRED` or `OBSERVED`

A branch is recommended for closing, even if its researcher said `continue`,
when any of these holds for the wave:

- it added fewer than 3 new tagged facts and resolved no unknowns
- more than 60% of its findings duplicated the tree
- it resolved no unknowns and more than 80% of its findings were `INFERRED`
  or `OBSERVED`

These are starting defaults. They are stored in `plan.json` so the user can
change them, and the end-to-end test is expected to adjust them.

### Closing

- A branch recommended for closing is closed automatically.
- The gate summary lists every branch closed in the wave with its reason.
- The user can reopen any closed branch.
- Unresolved unknowns from a closed branch go to `remaining_unknowns.md` with
  the reason.

## Gates and controls

The user is asked to approve at these points:

- the plan, after intake
- the entity type list, after stage 2
- the proposals, before every stage 4 research wave

Each stage 4 gate shows the branches closed, the branches open, the proposals,
and how many agents the next wave will use.

`plan.json` holds the depth cap per branch (default 4) and the maximum agents
per wave (default 4), so a wide tree cannot launch dozens of agents at once.
Approved tasks beyond the agent cap run in a following wave.

## State and scripts

All state is on disk. A session can be closed at any point and resumed.

Scripts print JSON to stdout and are called by the coordinator:

| Script | Purpose |
|---|---|
| `scaffold` | Create the workspace for a new subject |
| `add_session` | Create a session folder and its task list |
| `next_task` | Return the next incomplete task or tasks |
| `complete_task` | Mark a task done and append to the activity log |
| `status` | Report stage, task, and branch status |
| `validate` | Check entity files, provenance tags, and proposals |
| `score` | Count per-branch facts, unknowns, duplicates, and tiers |

They are ported from the GameAnalysis2 scripts where an equivalent exists.

## Failure handling

| Situation | Behaviour |
|---|---|
| A researcher fails or returns nothing | The task stays incomplete with the reason logged. It is retried once, then reported at the gate. It is never marked done. |
| Web search is unavailable | Stages 3 and 4 refuse to run and say why. They do not fall back to training knowledge. |
| The session is interrupted | The skill resumes at the first incomplete task. Raw files from an unfinished wave are kept and organized on resume. |
| Sources conflict within the same tier | Both values are recorded with their sources and flagged for the user. Neither is chosen silently. |
| Python is missing | The skill edits the JSON state directly and warns that validation and scoring were skipped. |

## Testing

- **Scripts.** Unit tests on fixture folders for scaffold, next task, complete
  task, status, proposal validation, and branch scoring.
- **Plan generator.** Run intake for a game and compare the generated plan
  with the hand-written 21-task template in `examples/games/`.
- **End to end.** Run one small real subject through all four stages with a
  depth cap of 2. Check that every claim is tagged, that no researcher wrote
  to `knowledge/`, and that at least one branch closed with a recorded reason.
- **Skill behaviour.** Pressure-test `SKILL.md` with subagents on the cases
  most likely to go wrong: skipping a gate, fabricating when search fails, and
  a researcher proposing vague sub-tasks.

## Out of scope for the first version

- Bundled domain packs
- An unattended headless loop
- Comparison across research projects
- Publishing to a plugin marketplace

The on-disk state format is the same one a headless loop would use, so that
can be added later without changing the rest.
