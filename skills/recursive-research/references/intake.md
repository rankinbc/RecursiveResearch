# Intake and plan

The goal is an approved `plan.json`. No research runs before that.

## 1. Ask

Ask these one at a time. Skip any the user has already answered.

1. What is the subject? Get it specific enough to tell versions apart (which
   edition, release, or period).
2. What is the research for? What should the user be able to do with the
   result?
3. How deep and how precise does it need to be? Ask for an example of a fact
   at the level of detail they want.
4. What sources or local material do they already have? Files in the project,
   repositories, documents, sites they trust.

## 2. Scaffold

    RR scaffold "<subject>"

If the subject has no Latin letters or digits, add `--slug <short-name>`.

## 3. Draft the plan

Edit `research/<slug>/plan.json`. Leave `schema_version`, `slug`, `created`,
`approvals`, `stages`, `sessions`, and `branches` alone. Fill in:

| Field | What to write |
|---|---|
| `goal` | What the research is for, in the user's terms. |
| `voice` | Who is writing and for whom, for example "an engineer writing a reference, not an encyclopedia entry". |
| `precision_bar` | What counts as specific enough, with the user's example. |
| `definition_of_done` | What the user must be able to do with the result. Researchers use this to judge when an unknown no longer matters. |
| `survey_tasks` | 10 to 20 tasks, each `{"title", "description"}`. See below. |
| `entity_types` | The kinds of thing the subject has many named instances of. |
| `provenance_mapping` | Concrete sources for `PRIMARY`, `EXPERT`, and `SECONDARY`. |
| `controls` | Keep the defaults unless the user asked for something else. |

**Survey tasks.** Always include these five, adapted to the subject:

- Overview: what it is, who made it, when, and why it matters
- End to end: how it works from start to finish in the normal case
- History and context: how it came to be and what it responded to
- Comparison with peers: what is similar, and what this does differently
- Lessons and influence: what it changed and what is still relevant

Add one task for each major system, component, or theme of this subject. Each
task must be researchable on its own, since the tasks run in parallel. Do not
add a final review task; assembly and review are added automatically.

**Entity types.** Every subject gets an entity pass, so name at least one. An
entity type is a category with several named instances that share comparable
properties: for a protocol, message types and error codes; for a company,
products and executives; for a game, weapons and enemies.

**Provenance mapping.** Name real sources, not categories. `PRIMARY` is the
thing itself. `EXPERT` is people with direct access who verified it.
`SECONDARY` is published writing about it. Put anything the user supplied
locally under the tier it deserves.

Where a subject has both an authoritative document and an informal one about
the same thing, such as a specification and its non-normative overview, name
them separately and give only the authoritative one `PRIMARY`. Researchers
disagree about the informal one unless the plan settles it.

`examples/games/plan-example.json` is a complete worked example for a video
game. Use it to judge the level of detail, not as content to copy.

## 4. Validate

    RR validate <slug> plan

Fix every error it reports.

## 5. Gate: the plan

Show the user the plan in readable form, not as raw JSON:

- the goal, voice, precision bar, and definition of done
- the survey tasks as a numbered list
- the entity types
- the provenance mapping as a table
- the depth cap and the agent cap, and that the survey will run one agent per
  task, at most the agent cap at a time

Ask them to approve or change it. Apply changes, validate again, and show the
changed parts again.

If the user told you up front to skip the approvals, still show the plan and
wait. Say that it is one short confirmation and that it decides how many
agents will run. Do not record an approval they have not given after seeing
the plan. When they approve:

    RR approve <slug> plan

Then start stage 1 with `references/survey.md`.
