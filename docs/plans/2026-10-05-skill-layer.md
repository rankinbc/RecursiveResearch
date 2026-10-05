# RecursiveResearch Skill Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the state engine into an installable Claude Code plugin: a manifest, two agents, one coordinator skill with per-stage references, and the briefs the agents receive.

**Architecture:** The skill is the coordinator. It asks the user for approval at each gate, dispatches `researcher` and `organizer` agents with filled-in briefs, and calls `scripts/rr.py` for every state change. `SKILL.md` stays short and points to one reference per stage, loaded only when that stage runs. Automated tests keep the documents, the briefs, and the script's commands consistent with each other; a real end-to-end run and pressure tests check behaviour.

**Tech Stack:** Claude Code plugin format (Markdown with frontmatter, JSON manifest). Tests use Python `unittest`.

**Spec:** `docs/specs/2026-10-04-recursive-research-design.md`

This is plan 2 of 2. It requires plan 1 (`docs/plans/2026-10-05-state-engine.md`) to be complete: the tests import `scripts/rr.py` and `scripts/rrlib/`.

## Global Constraints

- The plugin and skill are named `recursive-research`. Agents are `researcher` and `organizer`, dispatched as `recursive-research:researcher` and `recursive-research:organizer`.
- Templates use `{{PLACEHOLDER}}` syntax. Every placeholder must be documented in a reference file.
- Prompt files use indented code blocks, not fenced ones.
- `SKILL.md` stays under 130 lines. Detail belongs in `references/`.
- Every script command the documents mention must exist, and every command must be mentioned.
- The file shapes written in the templates must match the validators in `scripts/rrlib/validate.py`.
- Stages 3 and 4 never run without web search. Their briefs tell the agent to reply `SEARCH_UNAVAILABLE` and write nothing.
- No bundled domain packs, no headless loop, no marketplace publishing (out of scope in the spec).
- Run all tests from the repository root with `python -m unittest discover -s tests`.

## Decisions this plan makes where the spec was silent

The user should confirm these when reviewing the plan.

1. **Remembered claims in the survey are `OBSERVED`.** The spec requires a tag on every claim but stage 1 may draw on what the model knows. A claim with no source found in the session is tagged `OBSERVED` in stage 1 and must be `UNKNOWN` in stages 3 and 4.
2. **The researcher has the `Write` tool.** It needs it to write its output file, so its restriction to `raw/` rests on its instructions plus the engine's snapshot check, not on tool access alone. It has no `Edit` and no `Bash`. The organizer has no search tools and no `Bash`.
3. **Stage 2 is done by the organizer agent**, because it writes to `knowledge/` and needs no search.
4. **There is no gate after the survey or after enumeration.** The gates are the plan, the entity type list, and every wave of proposals, as in the spec.

## Review Focus

Conditions the spec implies but does not spell out, most likely first.

1. **A brief and a validator disagree about a file's shape**, so every agent's output is rejected. Pinned by `test_deepening_template_lists_exactly_the_engines_verdicts` in Task 3 and by the end-to-end run in Task 4, which exercises every shape.
2. **A document names a command or file that does not exist**, so the coordinator stalls. Pinned by `test_every_script_command_in_the_docs_is_real`, `test_every_reference_mentioned_exists` (Task 2) and `test_every_template_mentioned_exists_and_every_template_is_used` (Task 3).
3. **A placeholder is left unfilled** because no document says where its value comes from. Pinned by `test_every_placeholder_is_documented_in_a_reference` in Task 3.
4. **The plugin is installed somewhere the script path does not resolve.** Checked by hand in Task 4, Step 2, with the fix stated there.
5. **The coordinator skips a gate or completes a task the script refused.** Checked by the pressure tests in Task 5.

## File Structure

| File | Responsibility |
|---|---|
| `.claude-plugin/plugin.json` | Plugin manifest |
| `agents/researcher.md` | The research role and its rules |
| `agents/organizer.md` | The organizing role and its rules |
| `skills/recursive-research/SKILL.md` | The coordinator: rules, routing, the research loop, gates |
| `skills/recursive-research/references/intake.md` | Questions, drafting the plan, the plan gate |
| `skills/recursive-research/references/provenance.md` | Tiers, choosing one, writing tags |
| `skills/recursive-research/references/tree.md` | Knowledge tree conventions |
| `skills/recursive-research/references/state.md` | State file formats, for work without Python |
| `skills/recursive-research/references/survey.md` | Stage 1 procedure |
| `skills/recursive-research/references/entity-schema.md` | Stage 2 procedure and gate |
| `skills/recursive-research/references/entity-enumeration.md` | Stage 3 procedure |
| `skills/recursive-research/references/deepening.md` | Stage 4 procedure, gate, closing rules, consolidation |
| `skills/recursive-research/templates/research-*.md` | Briefs for the researcher, one per stage |
| `skills/recursive-research/templates/organize-*.md` | Briefs for the organizer, one per job |
| `skills/recursive-research/examples/games/plan-example.json` | Worked example of a generated plan |
| `tests/test_plugin_files.py`, `tests/test_skill_docs.py`, `tests/test_templates.py` | Consistency tests |
| `README.md` | Installation and use |

---

### Task 1: Plugin manifest and agents

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `agents/researcher.md`
- Create: `agents/organizer.md`
- Test: `tests/test_plugin_files.py`

**Interfaces:**
- Consumes: `helpers.REPO` from plan 1.
- Produces:
  - Agent types `recursive-research:researcher` (tools: Read, Glob, Grep, WebSearch, WebFetch, Write) and `recursive-research:organizer` (tools: Read, Glob, Grep, Write, Edit).
  - `test_plugin_files.frontmatter(path) -> dict[str, str]`, reused by Task 2's tests.
  - The reply `SEARCH_UNAVAILABLE: <what failed>`, which the coordinator in Task 2 checks for.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_plugin_files.py`:

```python
import json
import unittest

from helpers import REPO


def frontmatter(path):
    """Parse the simple 'key: value' block between the first two '---' lines."""
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---", f"{path.name} must start with frontmatter"
    end = lines.index("---", 1)
    return dict(line.split(": ", 1) for line in lines[1:end])


def tools(path):
    return {t.strip() for t in frontmatter(path)["tools"].split(",")}


class PluginFileTests(unittest.TestCase):
    def test_manifest_names_the_plugin(self):
        manifest = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "recursive-research")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue(manifest["description"])

    def test_agents_are_named_after_their_files(self):
        for name in ("researcher", "organizer"):
            meta = frontmatter(REPO / "agents" / f"{name}.md")
            self.assertEqual(meta["name"], name)
            self.assertTrue(meta["description"])

    def test_researcher_can_search_but_cannot_edit_or_run_commands(self):
        self.assertEqual(tools(REPO / "agents" / "researcher.md"),
                         {"Read", "Glob", "Grep", "WebSearch", "WebFetch", "Write"})

    def test_organizer_can_edit_but_cannot_search_or_run_commands(self):
        self.assertEqual(tools(REPO / "agents" / "organizer.md"),
                         {"Read", "Glob", "Grep", "Write", "Edit"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest discover -s tests -p "test_plugin_files.py"`
Expected: 4 errors, each a `FileNotFoundError`.

- [ ] **Step 3: Write the manifest**

Create `.claude-plugin/plugin.json`:

```json
{
  "name": "recursive-research",
  "description": "Research a subject to a chosen depth and leave behind a structured, source-tagged knowledge base. The research writes its own next-level backlog and stops each branch when it runs dry.",
  "version": "0.1.0",
  "author": {
    "name": "rankinbc1"
  }
}
```

- [ ] **Step 4: Write the researcher agent**

Create `agents/researcher.md`:

````markdown
---
name: researcher
description: Finds and extracts facts for one recursive-research task. Dispatched by the recursive-research skill with a filled-in brief; not for general use.
tools: Read, Glob, Grep, WebSearch, WebFetch, Write
---

You research one task for a recursive-research project and write one output file.

Your brief names the task, the output file, the provenance mapping, and the
format to write. Follow it exactly.

## Rules

- Write exactly one file: the output path in your brief. It is inside the
  session's `raw/` folder. Never create or change anything under `knowledge/`.
  Placing findings in the knowledge base is another agent's job.
- Tag every factual claim with a provenance tier. Use the mapping in your
  brief to decide the tier of each source. Do not choose tiers by feel.
- Never guess. If you cannot find a value, record it as unknown. A wrong
  number is worse than a missing one.
- Keep versions apart. If sources describe different versions, editions, or
  releases of the subject, say which one each fact belongs to.
- Record where each fact came from precisely enough for someone to find it
  again: a URL, a file and line, a document and section.

## If you cannot search

If your brief says web search is required and the search tools are missing or
fail, do not fall back to what you remember. Write nothing, and reply with one
line:

    SEARCH_UNAVAILABLE: <what failed>

## Your reply

After writing the file, reply in three lines or fewer: the output path, what
you found, and what you could not find. The file is the deliverable; do not
repeat its contents.
````

- [ ] **Step 5: Write the organizer agent**

Create `agents/organizer.md`:

````markdown
---
name: organizer
description: Integrates raw research output into the knowledge base for a recursive-research project. Dispatched by the recursive-research skill with a filled-in brief; not for general use.
tools: Read, Glob, Grep, Write, Edit
---

You organize research for a recursive-research project. Researchers have
written raw findings into a session's `raw/` folder. You are the only role
that writes to `knowledge/`.

Your brief names the job, the files to read, and the files to write. Follow it
exactly.

## Rules

- You do not research. You have no search tools. Work only from the raw files,
  the existing knowledge base, and the plan. If something is missing, record
  it as an unknown; do not fill it in from memory.
- One canonical copy. If a fact or table already exists in the knowledge base,
  do not write it again. Link to it.
- Keep every provenance tag. When you move a claim, its tier and source move
  with it.
- Resolve conflicts by tier: `PRIMARY > EXPERT > SECONDARY > INFERRED >
  OBSERVED`. The stronger tier wins and the weaker value is dropped. If two
  values conflict at the same tier, keep both with their sources and mark the
  line `CONFLICT` so the user can decide. Never pick one silently.
- Never edit files under `raw/`. They are the record of what was found.

## Your reply

Reply in five lines or fewer: what you wrote, what conflicts you found, and
anything the coordinator must tell the user. Do not repeat file contents.
````

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_plugin_files.py"`
Expected: `Ran 4 tests` and `OK`

- [ ] **Step 7: Validate the plugin**

Run: `claude plugin validate .`
Expected: validation passes with no errors. If it reports an unknown field in `plugin.json`, remove that field and run it again.

- [ ] **Step 8: Commit**

```bash
git add .claude-plugin/plugin.json agents/researcher.md agents/organizer.md tests/test_plugin_files.py
git commit -m "Add the plugin manifest and the researcher and organizer agents"
```

---

### Task 2: Coordinator skill and references

**Files:**
- Create: `skills/recursive-research/SKILL.md`
- Create: `skills/recursive-research/references/intake.md`
- Create: `skills/recursive-research/references/provenance.md`
- Create: `skills/recursive-research/references/tree.md`
- Create: `skills/recursive-research/references/state.md`
- Create: `skills/recursive-research/references/survey.md`
- Create: `skills/recursive-research/references/entity-schema.md`
- Create: `skills/recursive-research/references/entity-enumeration.md`
- Create: `skills/recursive-research/references/deepening.md`
- Test: `tests/test_skill_docs.py`

**Interfaces:**
- Consumes: every command of `scripts/rr.py` (listed in plan 1, Task 5); `rr.build_parser()`; `test_plugin_files.frontmatter`.
- Produces:
  - The abbreviation `RR` for `python3 "<base directory>/../../scripts/rr.py" --root research`.
  - The template file names Task 3 must create: `research-survey.md`, `research-entity.md`, `research-deepening.md`, `organize-survey.md`, `organize-schema.md`, `organize-bootstrap.md`, `organize-wave.md`, `organize-consolidate.md`.
  - The placeholder names Task 3's templates may use, documented in the "Filling" tables: `SUBJECT`, `GOAL`, `VOICE`, `PRECISION_BAR`, `DEFINITION_OF_DONE`, `PROVENANCE_MAPPING`, `WORKSPACE`, `SESSION`, `OUTPUT`, `TASK_ID`, `TASK_TITLE`, `TASK_DESCRIPTION`, `OTHER_TASKS`, `TYPE_NAME`, `TYPE_SCHEMA`, `EXPECTED_TYPES`, `UNKNOWN`, `EXPECTED_SOURCES`, `BRANCH`, `TARGET`, `BRIEF`, `NEXT_LEVEL`, `DEPTH_CAP`, `CLOSED_BRANCHES`.
  - `sessions/<session>/coordination_brief.md`, written by the organizer and passed to the next wave as `{{BRIEF}}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skill_docs.py`:

```python
import re
import sys
import unittest

from helpers import REPO
from test_plugin_files import frontmatter

sys.path.insert(0, str(REPO / "scripts"))
import rr  # noqa: E402

SKILL = REPO / "skills" / "recursive-research"
DOCS = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]
COMMANDS = set(rr.build_parser()._subparsers._group_actions[0].choices)


class SkillDocTests(unittest.TestCase):
    def test_skill_frontmatter(self):
        meta = frontmatter(SKILL / "SKILL.md")
        self.assertEqual(meta["name"], "recursive-research")
        self.assertTrue(meta["description"].startswith("Use when"))

    def test_skill_file_stays_short(self):
        lines = (SKILL / "SKILL.md").read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 130, "move detail into references/ so it loads only when needed")

    def test_every_reference_mentioned_exists(self):
        mentioned = set()
        for doc in DOCS:
            mentioned |= set(re.findall(r"references/([a-z-]+\.md)", doc.read_text(encoding="utf-8")))
        existing = {p.name for p in (SKILL / "references").glob("*.md")}
        self.assertEqual(mentioned - existing, set(), "mentioned but missing")
        self.assertEqual(existing - mentioned, set(), "present but never mentioned")

    def test_every_script_command_in_the_docs_is_real(self):
        for doc in DOCS:
            for command in re.findall(r"\bRR ([a-z][a-z-]*)", doc.read_text(encoding="utf-8")):
                self.assertIn(command, COMMANDS, f"{doc.name} mentions 'RR {command}'")

    def test_every_script_command_is_documented(self):
        text = "".join(doc.read_text(encoding="utf-8") for doc in DOCS)
        for command in sorted(COMMANDS):
            self.assertRegex(text, rf"\bRR {command}\b", f"'RR {command}' is never explained")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest discover -s tests -p "test_skill_docs.py"`
Expected: FAIL; all five tests error with `FileNotFoundError` because `SKILL.md` does not exist.

- [ ] **Step 3: Write the skill**

Create `skills/recursive-research/SKILL.md`:

````markdown
---
name: recursive-research
description: Use when the user wants a subject researched in depth into a structured, source-tagged knowledge base, or wants to resume or check a research project under research/. Covers starting a new subject, continuing one, and reporting status.
---

# Recursive Research

You are the coordinator. You run a four-stage pipeline that turns a subject
into a knowledge base under `research/<subject>/`. You dispatch agents, run
the bookkeeping script, and stop at every approval gate. You never do the
research or write to `knowledge/` yourself.

## Rules that are never relaxed

1. **No research before the plan is approved.** The user approves the plan,
   the entity type list, and every wave of proposals. An approval covers only
   what was shown.
2. **Researchers write only to `raw/`. Organizers alone write `knowledge/`.**
3. **Every claim carries a provenance tag.** `UNKNOWN` is a valid value. A
   guess is not.
4. **Stages 3 and 4 require web search.** If it is unavailable, stop the stage
   and tell the user. Never fall back to memory.
5. **A task is done only when the script accepts it.** If `complete-task`
   refuses, record the failure with `fail-task`. Never edit `passes` by hand
   to get past a refusal.
6. **Stages run in order:** survey, entity schema, entity enumeration,
   deepening.

## The script

All bookkeeping goes through one script, two folders above this skill's base
directory:

    python3 "<base directory>/../../scripts/rr.py" --root research <command> ...

Use `python` if `python3` is not found. This document writes that prefix as
`RR`. Every command prints JSON. Exit code 1 means validation found errors;
exit code 2 means the command could not run, and the JSON on stderr says why.

If Python is not installed, read `references/state.md`, edit the state files
directly, and tell the user that validation and scoring were skipped.

## What to do first

Run `RR status`. Then:

- **The user named a new subject:** read `references/intake.md` and follow it.
- **A subject exists:** run `RR status <slug>` and do what `next_step` says,
  using the reference for the stage in progress.
- **The user only asked for status:** report it and stop.

| Stage | Reference |
|---|---|
| Intake and plan | `references/intake.md` |
| 1. Survey | `references/survey.md` |
| 2. Entity schema | `references/entity-schema.md` |
| 3. Entity enumeration | `references/entity-enumeration.md` |
| 4. Deepening | `references/deepening.md` |

Read a stage's reference when that stage starts, not before. Agent briefs are
in `templates/`; fill every `{{PLACEHOLDER}}` before dispatching.
`references/provenance.md` and `references/tree.md` define the tags and the
tree layout that the briefs refer to.

## The research loop

Stages 1, 3 and 4 dispatch researchers the same way:

1. `RR next-task <slug>` returns the next batch. It is never larger than the
   plan's agent cap.
2. `RR snapshot <slug>`.
3. Dispatch one `recursive-research:researcher` agent per task, all in one
   message so they run in parallel. Give each the stage's research template,
   filled in for its task.
4. For each agent that returns:
   - It replied `SEARCH_UNAVAILABLE`: run `RR fail-task`, stop the stage, and
     tell the user.
   - Otherwise run `RR complete-task <slug> <id> "<one-line summary>"`. If the
     script refuses, run `RR fail-task <slug> <id> "<the script's reason>"`.
5. `RR check-snapshot <slug>`. If it reports violations, a researcher wrote to
   `knowledge/`. Stop, show the user the files, and do not continue until they
   decide what to do.
6. Repeat from step 1 until the batch is empty or only a solo task remains.

A failed task is offered once more by `next-task`. After a second failure it
appears under `blocked`; report blocked tasks to the user at the next gate.

## Gates

At a gate, show the user what they are approving, say what happens next and
how many agents it will use, and wait. Record plan and entity approvals with
`RR approve`. Proposal approvals are recorded by setting each proposal's
`status` to `approved` or `skipped`.

## Resuming

All state is on disk. If a session was interrupted, `RR status <slug>` says
where to continue. Raw files from an unfinished wave are kept; finish the
wave's remaining tasks, then run the organizer as usual.
````

- [ ] **Step 4: Write the intake reference**

Create `skills/recursive-research/references/intake.md`:

````markdown
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
changed parts again. When they approve:

    RR approve <slug> plan

Then start stage 1 with `references/survey.md`.
````

- [ ] **Step 5: Write the provenance reference**

Create `skills/recursive-research/references/provenance.md`:

````markdown
# Provenance

Every factual claim in the knowledge base carries exactly one tier.

| Tier | Meaning |
|---|---|
| `PRIMARY` | The thing itself: source code, the binary, the original document, raw data |
| `EXPERT` | Verified by practitioners with direct access |
| `SECONDARY` | Published guides, references, wikis |
| `INFERRED` | Derived from other tagged facts |
| `OBSERVED` | Seen but not confirmed |
| `UNKNOWN` | Needed but not found |

Conflicts are resolved by precedence, strongest first:

    PRIMARY > EXPERT > SECONDARY > INFERRED > OBSERVED

## Choosing a tier

The plan's `provenance_mapping` lists the concrete sources that count as
`PRIMARY`, `EXPERT`, and `SECONDARY` for this subject. Find the source in the
mapping and use its tier. If a source is not in the mapping, use the tier of
the most similar source that is, and name the source exactly.

- `INFERRED` is for a conclusion you derived. Say what it was derived from.
- `OBSERVED` is for something seen once or reported without confirmation.
- Something you remember but found no source for in this session is not a
  finding. In stage 1 it may be written as `OBSERVED`. In stages 3 and 4 it
  must be recorded as `UNKNOWN`.

## Writing tags

In Markdown, put the tag after the claim:

    The header is 12 bytes [PRIMARY]. Retries are capped at about five [OBSERVED].
    The backoff multiplier is not documented [UNKNOWN: est 1.5-2].

An unknown may carry an estimated range after a colon.

In a JSON leaf file, put the tier and source in `_meta`:

    {
      "_meta": {
        "provenance": "PRIMARY",
        "source": "RFC 9999, section 4.2",
        "last_updated": "2026-10-04"
      },
      "max_frame_bytes": 16384
    }

`_meta.provenance` is the tier of the weakest value in the file. If the file
mixes tiers, split it or add a per-field `provenance` object.

In an entity roster, each entity has a `provenance` field: one tier for the
whole entity, or an object giving a tier for each property. A property whose
value is `null` must be `UNKNOWN`.
````

- [ ] **Step 6: Write the tree reference**

Create `skills/recursive-research/references/tree.md`:

````markdown
# The knowledge tree

`knowledge/tree/` is a hierarchy in which each level adds detail. The deeper
you go, the more precise the content.

    knowledge/tree/
      README.md               # the subject, how it works end to end, index of branches
      <branch>/
        README.md             # how this part works, and links deeper
        <sub-branch>/
          README.md           # detailed behaviour
          frame_sizes.json    # leaf: exact values
          retry_algorithm.md  # leaf: a formula or algorithm

Depth varies by branch. A simple branch may be two levels; a complex one may
be five. Let the content decide.

A **branch** is a folder path relative to `knowledge/tree/`, such as `wire` or
`wire/framing`. Closing a branch closes everything beneath it.

## Every folder has a README.md

It must:

1. Summarize what this level covers in one to three paragraphs.
2. State the key facts at this level of detail, each tagged.
3. Link to each deeper file and folder with a one-line description.
4. End with a `## Known Unknowns` section: a checklist of specific facts that
   are still missing. Write `- none` if there are none.

Each unknown must be one concrete missing fact:

    ## Known Unknowns
    - [ ] The maximum frame length in bytes
    - [ ] Whether the retry timer resets after a partial response

Not "more detail on framing".

## Leaf files

Leaves hold exact content, not summaries.

- **JSON** for tables: values, lists, lookup tables. Must have a `_meta`
  object with `provenance` and `source`.
- **Markdown** for formulas and algorithms. Include a prose explanation,
  pseudocode, and a worked example with real values. Tag every number.

Name files after what they hold, in snake_case: `retry_algorithm.md`,
`frame_sizes.json`. Never `data.json` or `notes.md`.

## Reference, do not duplicate

If `knowledge/entities/<type>.json` already holds the data, link to it. If two
branches need the same fact, it lives in one and the other links to it.
````

- [ ] **Step 7: Write the state reference**

Create `skills/recursive-research/references/state.md`:

````markdown
# State files

Read this only when Python is unavailable and you must edit state by hand, or
when you need to explain a file to the user.

## Layout

    research/<slug>/
      plan.json
      knowledge/
        spec.md
        entities.json
        entities/<type_id>.json
        tree/
        remaining_unknowns.md
      sessions/<session>/
        tasks.json
        activity.md
        raw/
        proposals/level_<N>.json
        ledger.json              # deepening waves only
        knowledge_snapshot.json

Session names are `<date>_<stage>`, or `<date>_deepening_w<NN>` for deepening.
Wave `w00` is the bootstrap. `plan.json` lists sessions in order under
`sessions`; the last one is current.

## plan.json

Besides the fields intake fills in:

- `approvals`: `{"plan": bool, "entity_types": bool}`
- `stages`: each of `survey`, `entity_schema`, `entity_enumeration`,
  `deepening` is `pending`, `in_progress`, or `done`
- `branches`: `{"<branch>": {"status": "open" | "closed", "level": N,
  "reason": "...", "session": "..."}}`

## tasks.json

    {"session": "...", "stage": "...", "tasks": [ ... ]}

Each task has `id`, `title`, `description`, `output` (path relative to the
workspace), `solo`, `passes`, `attempts`, `last_error`, `verdict`, and for
deepening tasks `branch`, `level`, `target`, `unknown`, `expected_sources`.

- A task is done when `passes` is true. Only set it after confirming the
  `output` file exists and is not empty.
- A failed attempt adds 1 to `attempts` and sets `last_error`. At 2 attempts
  the task is blocked.
- A `solo` task runs alone, after every task before it is done or blocked.

Append one line to `activity.md` for every completion or failure.

## proposals/level_N.json

    {"level": N, "proposals": [{
      "id": "...", "title": "...", "description": "...",
      "branch": "wire/framing",
      "target_file": "knowledge/tree/wire/framing/frame_sizes.json",
      "unknown_being_resolved": "The maximum frame length in bytes",
      "expected_sources": ["RFC 9999, section 4"],
      "level": N,
      "status": "proposed"
    }]}

`status` is `proposed`, `approved`, `skipped`, or `dropped`.

## ledger.json

    {"entries": [{"task_id": "...", "finding": 0,
                  "disposition": "new" | "duplicate" | "conflict",
                  "placed_in": "knowledge/tree/..."}]}

One entry for every finding in every completed task of the wave.

## Without the script

Apply the closing rules in `references/deepening.md` by counting from the raw
files and the ledger yourself, and tell the user the counts were done by hand.
````

- [ ] **Step 8: Write the survey reference**

Create `skills/recursive-research/references/survey.md`:

````markdown
# Stage 1: survey

Produces `knowledge/spec.md`: a broad prose overview, one section per task.

## Steps

1. `RR add-session <slug> survey`. This creates one task per survey task in
   the plan, plus a final `assemble` task.
2. Run the research loop from `SKILL.md` with `templates/research-survey.md`.
   Researchers may use what they know as well as search in this stage, but
   every claim is still tagged.
3. When `next-task` returns only the `assemble` task, dispatch one
   `recursive-research:organizer` agent with `templates/organize-survey.md`.
4. `RR complete-task <slug> assemble "<summary>"`.
5. If any survey task is blocked, tell the user which sections are missing
   and ask whether to retry them or continue without them.
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
````

- [ ] **Step 9: Write the entity schema reference**

Create `skills/recursive-research/references/entity-schema.md`:

````markdown
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
````

- [ ] **Step 10: Write the entity enumeration reference**

Create `skills/recursive-research/references/entity-enumeration.md`:

````markdown
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
````

- [ ] **Step 11: Write the deepening reference**

Create `skills/recursive-research/references/deepening.md`:

````markdown
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
````

- [ ] **Step 12: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -p "test_skill_docs.py"`
Expected: `Ran 5 tests` and `OK`

- [ ] **Step 13: Commit**

```bash
git add skills/recursive-research/SKILL.md skills/recursive-research/references tests/test_skill_docs.py
git commit -m "Add the coordinator skill and its stage references"
```

---

### Task 3: Agent briefs and the worked example

**Files:**
- Create: `skills/recursive-research/templates/research-survey.md`
- Create: `skills/recursive-research/templates/research-entity.md`
- Create: `skills/recursive-research/templates/research-deepening.md`
- Create: `skills/recursive-research/templates/organize-survey.md`
- Create: `skills/recursive-research/templates/organize-schema.md`
- Create: `skills/recursive-research/templates/organize-bootstrap.md`
- Create: `skills/recursive-research/templates/organize-wave.md`
- Create: `skills/recursive-research/templates/organize-consolidate.md`
- Create: `skills/recursive-research/examples/games/plan-example.json`
- Test: `tests/test_templates.py`

**Interfaces:**
- Consumes: the template names and placeholder names Task 2 documents; `validate.VERDICTS`, `validate.validate_plan`, `store.default_plan` from plan 1.
- Produces: the briefs. The JSON shapes they show are the ones plan 1's validators accept:
  - `research-entity.md` shows the entity roster shape checked by `validate_entity_file`.
  - `research-deepening.md` shows the research result shape checked by `validate_raw`.
  - `organize-schema.md` shows the `entities.json` shape checked by `validate_entity_schema`.
  - `organize-bootstrap.md` and `organize-wave.md` show the proposals shape checked by `validate_proposals`, and `organize-wave.md` shows the ledger shape read by `scoring.score_session`.

The worked example is this project's origin: the 21-task video game survey template from the GameAnalysis2 repository, converted to the plan format. Its final review task is omitted because assembly and review are added automatically, leaving 20 tasks.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_templates.py`:

```python
import json
import re
import unittest

from helpers import REPO
from rrlib import store, validate

SKILL = REPO / "skills" / "recursive-research"
TEMPLATES = sorted((SKILL / "templates").glob("*.md"))
DOC_TEXT = "".join(p.read_text(encoding="utf-8")
                   for p in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")])


class TemplateTests(unittest.TestCase):
    def test_every_template_mentioned_exists_and_every_template_is_used(self):
        mentioned = set(re.findall(r"templates/([a-z-]+\.md)", DOC_TEXT))
        existing = {p.name for p in TEMPLATES}
        self.assertEqual(mentioned - existing, set(), "mentioned but missing")
        self.assertEqual(existing - mentioned, set(), "present but never mentioned")

    def test_every_placeholder_is_documented_in_a_reference(self):
        documented = set(re.findall(r"\{\{([A-Z_]+)\}\}", DOC_TEXT))
        for template in TEMPLATES:
            used = set(re.findall(r"\{\{([A-Z_]+)\}\}", template.read_text(encoding="utf-8")))
            self.assertEqual(used - documented, set(), f"{template.name} uses undocumented placeholders")

    def test_research_templates_refuse_to_work_without_search(self):
        for name in ("research-entity.md", "research-deepening.md"):
            self.assertIn("SEARCH_UNAVAILABLE", (SKILL / "templates" / name).read_text(encoding="utf-8"))

    def test_deepening_template_lists_exactly_the_engines_verdicts(self):
        text = (SKILL / "templates" / "research-deepening.md").read_text(encoding="utf-8")
        listed = set(re.findall(r"^\| `([a-z]+)` \|", text, re.MULTILINE))
        self.assertEqual(listed, set(validate.VERDICTS))

    def test_the_games_example_is_a_valid_plan(self):
        example = json.loads((SKILL / "examples" / "games" / "plan-example.json").read_text(encoding="utf-8"))
        plan = store.default_plan("Example Game", "example-game")
        plan.update({k: v for k, v in example.items() if not k.startswith("_")})
        self.assertEqual(validate.validate_plan(plan), [])
        self.assertEqual(len(plan["survey_tasks"]), 20)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest discover -s tests -p "test_templates.py"`
Expected: FAIL; `test_every_template_mentioned_exists_and_every_template_is_used` reports eight templates as "mentioned but missing", and three tests error with `FileNotFoundError`.

- [ ] **Step 3: Write the survey research brief**

Create `skills/recursive-research/templates/research-survey.md`:

````markdown
# Survey task: {{TASK_TITLE}}

You are researching **{{SUBJECT}}**. This is one section of a broad survey.

**What the research is for:** {{GOAL}}

**Your task:** {{TASK_DESCRIPTION}}

**Other sections, written by other agents (stay out of their scope):**
{{OTHER_TASKS}}

## Write

Write one Markdown section to `{{WORKSPACE}}/{{OUTPUT}}`. Start it with
`## {{TASK_TITLE}}`.

- Voice: {{VOICE}}
- Precision: {{PRECISION_BAR}}
- Be specific: numbers, names, dates, and tables for comparisons.
- Explain why things are the way they are, not only what they are.
- Say how this part connects to the other sections.
- Tag every factual claim with a provenance tier, like `[SECONDARY]`.

## Provenance

Tiers, strongest first: `PRIMARY`, `EXPERT`, `SECONDARY`, `INFERRED`,
`OBSERVED`, `UNKNOWN`. For this subject:

{{PROVENANCE_MAPPING}}

Search to confirm what you can. Something you remember but found no source
for is `[OBSERVED]`. Something you could not establish is `[UNKNOWN]`. Do not
present a guess as a fact.

End the section with a `### Open questions` list of specific facts you could
not find.
````

- [ ] **Step 4: Write the entity research brief**

Create `skills/recursive-research/templates/research-entity.md`:

````markdown
# Enumerate every {{TYPE_NAME}}

You are researching **{{SUBJECT}}**. Produce the complete list of every
{{TYPE_NAME}}, with exact values for every property.

**Web search is required.** Search before you write anything. If the search
tools are missing or fail, write nothing and reply with the single line
`SEARCH_UNAVAILABLE: <what failed>`. Do not list instances from memory.

## Schema

{{TYPE_SCHEMA}}

`{{WORKSPACE}}/knowledge/spec.md` has background. It is a starting point, not
a complete list; find the instances it does not mention.

## Write

Write JSON to `{{WORKSPACE}}/{{OUTPUT}}` in exactly this shape:

    {
      "entity_type": "{{TYPE_NAME}}",
      "count": 2,
      "_meta": {"last_updated": "YYYY-MM-DD", "sources": ["..."]},
      "entities": [
        {
          "name": "Instance name",
          "properties": {"<property>": <value>, "<property>": null},
          "provenance": {"<property>": "PRIMARY", "<property>": "UNKNOWN"},
          "notes": null
        }
      ]
    }

- Every entity has every property in the schema, and no others.
- A value you could not find is `null`, and its tier is `UNKNOWN`.
- Numbers are numbers, not strings.
- `provenance` gives a tier for every property. If every property of an
  entity came from the same source, it may be a single tier string.
- `count` equals the number of entities.
- `notes` is one sentence or `null`. Use it to say which version a value
  belongs to when versions differ.

## Provenance

Tiers, strongest first: `PRIMARY`, `EXPERT`, `SECONDARY`, `INFERRED`,
`OBSERVED`, `UNKNOWN`. For this subject:

{{PROVENANCE_MAPPING}}

Completeness matters, but not more than accuracy. A `null` is correct when
you do not know. An invented value is a defect.
````

- [ ] **Step 5: Write the deepening research brief**

Create `skills/recursive-research/templates/research-deepening.md`:

````markdown
# Research task {{TASK_ID}}: {{TASK_TITLE}}

You are researching **{{SUBJECT}}**. Resolve one specific unknown.

**The unknown:** {{UNKNOWN}}

**Context:** {{TASK_DESCRIPTION}}

**Where to look first:** {{EXPECTED_SOURCES}}

**Branch:** `{{BRANCH}}`. Your findings will be placed in `{{TARGET}}` by
another agent. Read `{{WORKSPACE}}/knowledge/tree/{{BRANCH}}/` first so you do
not report what is already there.

**Web search is required.** If the search tools are missing or fail, write
nothing and reply with the single line `SEARCH_UNAVAILABLE: <what failed>`.

## Who owns what

{{BRIEF}}

Stay inside your own task. If you find something that belongs to another
task, add it as a finding anyway and say so in the claim.

## Write

Write JSON to `{{WORKSPACE}}/{{OUTPUT}}` in exactly this shape:

    {
      "task_id": "{{TASK_ID}}",
      "branch": "{{BRANCH}}",
      "verdict": "continue",
      "verdict_reason": "",
      "findings": [
        {"claim": "The maximum frame length is 16384 bytes", "tier": "PRIMARY",
         "source": "RFC 9999, section 4.2", "detail": ""}
      ],
      "unknowns_resolved": ["The maximum frame length in bytes"],
      "unknowns_opened": ["Whether extension frames may exceed the maximum"],
      "unknowns_remaining": ["Whether extension frames may exceed the maximum"],
      "sources_searched": ["RFC 9999", "vendor implementation notes"],
      "proposals": []
    }

- One finding per fact. Put formulas, pseudocode, or tables in `detail`.
- Every finding has a `tier` and a `source`. A finding cannot be `UNKNOWN`;
  list what you could not find under `unknowns_remaining`.
- `unknowns_opened` are new questions your research raised.
  `unknowns_remaining` is everything still unanswered when you stop,
  including the opened ones.

## Provenance

Tiers, strongest first: `PRIMARY`, `EXPERT`, `SECONDARY`, `INFERRED`,
`OBSERVED`. For this subject:

{{PROVENANCE_MAPPING}}

## Verdict

End with exactly one verdict. Choose honestly; stopping is a good outcome
when there is nothing left to find.

| Verdict | Use when | You must also give |
|---|---|---|
| `exhausted` | The unknown is resolved and nothing new is worth asking | `unknowns_remaining` empty |
| `irreducible` | Unknowns remain but the available sources do not hold the answer | `sources_searched`: everything you tried |
| `sufficient` | Unknowns remain but they do not matter for the goal below | `verdict_reason`: which unknowns, and why |
| `continue` | A specific further fact is findable and matters | at least one entry in `proposals` |

**The goal that decides what matters:** {{GOAL}}
**Done means:** {{DEFINITION_OF_DONE}}
**Precision needed:** {{PRECISION_BAR}}

## Proposals

Only with `continue`. Each proposal is one task for a later researcher:

    {"title": "Short title",
     "description": "What to find and why it matters",
     "unknown_being_resolved": "One concrete missing fact",
     "expected_sources": ["Where the answer is likely to be"]}

`unknown_being_resolved` must name a single fact that someone could look up,
such as "the retry backoff multiplier". "More detail on retries" will be
rejected. If you cannot name the fact and where it might be found, the right
verdict is `irreducible` or `sufficient`, not `continue`.
````

- [ ] **Step 6: Write the survey assembly brief**

Create `skills/recursive-research/templates/organize-survey.md`:

````markdown
# Assemble the survey for {{SUBJECT}}

Researchers wrote one section each into `{{WORKSPACE}}/sessions/{{SESSION}}/raw/`.
Assemble them into `{{WORKSPACE}}/knowledge/spec.md`.

Read `{{WORKSPACE}}/sessions/{{SESSION}}/tasks.json` for the task order. A
task whose `passes` is false has no section; leave it out and list it under
"Missing sections".

## Write `knowledge/spec.md`

1. A title: `# {{SUBJECT}} -- Survey`.
2. A table of contents linking to every section.
3. The sections, in task order, as the researchers wrote them. Keep every
   provenance tag.
4. Fix inconsistencies between sections. Where two sections give different
   values for the same fact, keep the stronger tier
   (`PRIMARY > EXPERT > SECONDARY > INFERRED > OBSERVED`). At the same tier,
   keep both and mark the line `CONFLICT`.
5. Add cross-references where one section relies on another.
6. Merge every section's "Open questions" into one `## Open questions` list
   at the end, removing repeats.
7. If any sections are missing, add `## Missing sections` naming them.

Do not add facts of your own. Do not remove a claim because it is uncertain;
its tag already says so.
````

- [ ] **Step 7: Write the entity schema brief**

Create `skills/recursive-research/templates/organize-schema.md`:

````markdown
# Identify the entity types of {{SUBJECT}}

Read `{{WORKSPACE}}/knowledge/spec.md` and write
`{{WORKSPACE}}/knowledge/entities.json`.

This is a schema pass. Identify the kinds of thing that exist and what
properties they have. A later stage lists every instance.

## What counts as an entity type

A category with several named instances that share comparable properties.
Tables in the survey almost always indicate one.

Not an entity type: something there is only one of, an abstract principle, or
a fact about the subject as a whole.

The plan expected these types: {{EXPECTED_TYPES}}. Treat that as a starting
list. Add types the survey reveals, and leave out expected types the survey
shows do not exist.

## Write

    {
      "entity_types": [
        {
          "name": "MessageType",
          "description": "One sentence on what this is",
          "estimated_count": 12,
          "examples": ["HELLO", "PING"],
          "properties": [
            {"name": "code", "type": "number", "unit": null, "description": "brief"}
          ]
        }
      ],
      "relationships": [
        {"type": "replies_to", "from_type": "MessageType", "to_type": "MessageType",
         "description": "How the types relate"}
      ]
    }

- Names in PascalCase, using the subject's own terms.
- Two or three examples per type, only to confirm the type exists.
- Property names in snake_case. Include every property a complete record of
  one instance would need, even where the survey has no values yet.
- `type` is `number`, `string`, `boolean`, or `array`.
- Be thorough about types. A type missed here is never enumerated.
````

- [ ] **Step 8: Write the bootstrap brief**

Create `skills/recursive-research/templates/organize-bootstrap.md`:

````markdown
# Build the knowledge tree for {{SUBJECT}}

Build `{{WORKSPACE}}/knowledge/tree/` from what is already known, then write
the first research proposals.

Read:

- `{{WORKSPACE}}/knowledge/spec.md`
- `{{WORKSPACE}}/knowledge/entities.json` and `{{WORKSPACE}}/knowledge/entities/`
- `{{WORKSPACE}}/plan.json` for the goal and the precision bar

**The goal:** {{GOAL}}
**Precision needed:** {{PRECISION_BAR}}

## 1. Build the tree

Create one folder per major system, component, or theme. Let the subject
decide the branches; do not copy the survey's section list. Two levels is
enough for now.

Every folder gets a `README.md` that:

1. Summarizes what the folder covers in one to three paragraphs.
2. States the key facts already known, each with its provenance tag carried
   over from the survey.
3. Links to deeper folders and to entity files such as
   `../../entities/message_type.json`. Do not copy entity data into the tree.
4. Ends with `## Known Unknowns`: a checklist of specific missing facts that
   the goal needs. Write `- none` if there are none.

Also write `{{WORKSPACE}}/knowledge/tree/README.md`: what the subject is, how
it works end to end, an index of the branches, and its own `## Known
Unknowns`.

Each unknown is one concrete fact someone could look up, such as "the
maximum frame length in bytes". Not "more detail on framing".

## 2. Write proposals

Write `{{WORKSPACE}}/sessions/{{SESSION}}/proposals/level_1.json`:

    {"level": 1, "proposals": [{
      "id": "framing-max-length",
      "title": "Find the maximum frame length",
      "description": "What to find and why the goal needs it",
      "branch": "wire/framing",
      "target_file": "knowledge/tree/wire/framing/frame_sizes.json",
      "unknown_being_resolved": "The maximum frame length in bytes",
      "expected_sources": ["RFC 9999, section 4"],
      "level": 1,
      "status": "proposed"
    }]}

- One proposal per unknown that matters for the goal. Leave out unknowns the
  goal does not need.
- `id` uses lowercase letters, digits, and hyphens, and is unique.
- `branch` is the folder path under `knowledge/tree/`. `target_file` must be
  inside that folder.
- Give every proposal a different scope. Two proposals must never chase the
  same fact.

## 3. Write the coordination brief

Write `{{WORKSPACE}}/sessions/{{SESSION}}/coordination_brief.md`: for each
proposal id, one line saying what it owns and which neighbouring proposal
owns the things it might be tempted to cover.
````

- [ ] **Step 9: Write the wave organizing brief**

Create `skills/recursive-research/templates/organize-wave.md`:

````markdown
# Organize research wave {{SESSION}} for {{SUBJECT}}

Researchers wrote results into `{{WORKSPACE}}/sessions/{{SESSION}}/raw/`, one
JSON file per task. Place the findings in `{{WORKSPACE}}/knowledge/tree/`,
record what you did with each one, and write the next proposals.

Read `{{WORKSPACE}}/sessions/{{SESSION}}/tasks.json`. Process only tasks whose
`passes` is true. Each task names its `branch` and `target` file.

## 1. Place every finding

For each finding in each raw file, decide one disposition:

- **new**: the tree does not have this fact. Write it into the task's target
  file, or a better-fitting file in the same branch. Keep its tier and source.
- **duplicate**: the tree or an entity file already has this fact at an equal
  or stronger tier. Do not write it again.
- **conflict**: the tree has a different value for the same fact. The
  stronger tier wins (`PRIMARY > EXPERT > SECONDARY > INFERRED > OBSERVED`).
  If the new finding is stronger, replace the old value. At the same tier,
  keep both with their sources and mark the line `CONFLICT`.

Follow the tree conventions: a `README.md` in every folder ending with
`## Known Unknowns`; JSON leaves with `_meta.provenance` and `_meta.source`;
Markdown leaves with tagged claims; file names that say what the file holds.

A fact that fits two branches lives in one, and the other links to it.

## 2. Write the ledger

Write `{{WORKSPACE}}/sessions/{{SESSION}}/ledger.json` with one entry for
every finding of every completed task, in order:

    {"entries": [
      {"task_id": "framing-max-length", "finding": 0, "disposition": "new",
       "placed_in": "knowledge/tree/wire/framing/frame_sizes.json"}
    ]}

`finding` is the finding's position in the raw file, starting at 0. For a
duplicate, `placed_in` is where the existing copy is. Be strict: a fact
restated in different words is still a duplicate. These counts decide which
branches close.

## 3. Update Known Unknowns

In each README you touched: tick off unknowns listed in the raw files'
`unknowns_resolved`, and add those in `unknowns_remaining` that are not
already there.

## 4. Write the next proposals

Collect the `proposals` from raw files whose verdict is `continue`. Then
write `{{WORKSPACE}}/sessions/{{SESSION}}/proposals/level_{{NEXT_LEVEL}}.json`:

    {"level": {{NEXT_LEVEL}}, "proposals": [{
      "id": "...", "title": "...", "description": "...",
      "branch": "wire/framing",
      "target_file": "knowledge/tree/wire/framing/extension_frames.md",
      "unknown_being_resolved": "One concrete missing fact",
      "expected_sources": ["..."],
      "level": {{NEXT_LEVEL}},
      "status": "proposed"
    }]}

- Merge proposals that chase the same fact. Each remaining proposal owns a
  scope no other proposal touches.
- Add a proposal for any gap that falls between branches and that no
  researcher owned. Assign it to the most relevant branch.
- Drop a proposal whose unknown is not one concrete fact, or that the goal
  does not need.
- Do not write proposals for these closed branches: {{CLOSED_BRANCHES}}
- Do not write any proposals if {{NEXT_LEVEL}} is greater than the depth cap
  of {{DEPTH_CAP}}. Write the file with an empty list.
- `id` uses lowercase letters, digits, and hyphens, and is unique.
  `target_file` must be inside `knowledge/tree/<branch>/`.

**The goal:** {{GOAL}}

## 5. Write the coordination brief

Write `{{WORKSPACE}}/sessions/{{SESSION}}/coordination_brief.md`: for each
proposal id, one line saying what it owns and which neighbouring proposal
owns the things it might be tempted to cover.
````

- [ ] **Step 10: Write the consolidation brief**

Create `skills/recursive-research/templates/organize-consolidate.md`:

````markdown
# Consolidate the knowledge base for {{SUBJECT}}

The research waves are finished. Make `{{WORKSPACE}}/knowledge/` consistent
and navigable. Do not add facts.

## 1. Cross-reference

Walk `{{WORKSPACE}}/knowledge/tree/`. Wherever one branch relies on a fact
held in another branch or in `knowledge/entities/`, add a link. Where the same
fact appears twice, keep the copy with the stronger tier and replace the
other with a link.

## 2. Check every README

Each folder's `README.md` must summarize its level, link to everything
beneath it, and end with `## Known Unknowns`. Update the top-level
`knowledge/tree/README.md` so its index lists every branch.

## 3. Finish `remaining_unknowns.md`

`{{WORKSPACE}}/knowledge/remaining_unknowns.md` already has a section for each
branch that was closed, with the reason. Keep those sections as they are. Add
a final section, `## Open at the end`, listing every unticked item still under
a `## Known Unknowns` heading in the tree that is not already in the file,
with the path of the README it came from.

## 4. List conflicts

Search the tree for lines marked `CONFLICT`. In your reply, list each one
with its file, so the coordinator can show them to the user.
````

- [ ] **Step 11: Write the worked example**

Create `skills/recursive-research/examples/games/plan-example.json`:

```json
{
  "_about": "Worked example of the plan fields intake generates, for a video game. Tasks marked customize are replaced with the game's own systems.",
  "goal": "Document the game precisely enough that a developer could rebuild its systems",
  "voice": "A game designer documenting specs, not an encyclopedia entry: specific numbers, tables for comparisons, and design rationale",
  "precision_bar": "Exact stats, costs, formulas and timings; approximate values are marked as such",
  "definition_of_done": "Every major system has its formulas and data tables, and what remains unknown is listed with the reason",
  "survey_tasks": [
    {
      "title": "Game Overview & History",
      "description": "Developer background, release year and context, platform, development story, reception, legacy and cultural impact",
      "customize": false
    },
    {
      "title": "Core Gameplay Loop",
      "description": "Primary gameplay structure, how a typical session flows, what the player actually does moment-to-moment, the core engagement loop",
      "customize": false
    },
    {
      "title": "Core System 1",
      "description": "Replace with the game's primary system (e.g., combat, exploration, building, puzzle-solving)",
      "customize": true
    },
    {
      "title": "Core System 2",
      "description": "Replace with a major game system (e.g., world/setting, factions, character progression)",
      "customize": true
    },
    {
      "title": "Core System 3",
      "description": "Replace with a major game system (e.g., equipment, ships, resources, magic)",
      "customize": true
    },
    {
      "title": "Core System 4",
      "description": "Replace with a major game system",
      "customize": true
    },
    {
      "title": "Secondary System 1",
      "description": "Replace with a supporting system (e.g., economy, crafting, dialogue)",
      "customize": true
    },
    {
      "title": "Secondary System 2",
      "description": "Replace with a supporting system",
      "customize": true
    },
    {
      "title": "Secondary System 3",
      "description": "Replace with a supporting system",
      "customize": true
    },
    {
      "title": "Narrative/Story",
      "description": "Replace with story structure, characters, narrative design, branching paths if applicable",
      "customize": true
    },
    {
      "title": "World/Level Design",
      "description": "Replace with world structure, level design, navigation, areas, progression gates",
      "customize": true
    },
    {
      "title": "Enemies/Challenges",
      "description": "Replace with opposition design -- enemies, bosses, obstacles, difficulty drivers",
      "customize": true
    },
    {
      "title": "Progression & Economy",
      "description": "Replace with how the player grows stronger -- leveling, unlocks, currency, upgrades",
      "customize": true
    },
    {
      "title": "Unique Feature",
      "description": "Replace with the game's most distinctive or innovative system (e.g., time travel, modding, multiplayer)",
      "customize": true
    },
    {
      "title": "Technical Design",
      "description": "Engine/hardware capabilities, rendering approach, sound/music design, save system, performance characteristics",
      "customize": false
    },
    {
      "title": "UI & Controls",
      "description": "Control scheme, HUD elements, menu systems, how the game communicates information to the player, feedback systems",
      "customize": false
    },
    {
      "title": "Difficulty & Game Feel",
      "description": "Difficulty curve, balance analysis, common sticking points, skill vs progression, how the game 'feels' to play",
      "customize": false
    },
    {
      "title": "Additional Topic",
      "description": "Replace with another notable aspect -- could be multiplayer, modding, distribution model, accessibility, or merge with another task if 18 topics suffice",
      "customize": true
    },
    {
      "title": "Comparison to Contemporaries",
      "description": "How this game compared to peers of its era, what made it unique, where contemporaries excelled instead",
      "customize": false
    },
    {
      "title": "Design Lessons & Influence",
      "description": "What the game pioneered, lasting design principles, influence on later games, why it's remembered or forgotten",
      "customize": false
    }
  ],
  "entity_types": [
    "Weapon",
    "Enemy",
    "Item",
    "CharacterClass",
    "Region"
  ],
  "provenance_mapping": {
    "PRIMARY": [
      "ROM or binary disassembly",
      "data extracted by randomizer or modding tools",
      "the game's own data files"
    ],
    "EXPERT": [
      "speedrun and TAS documentation",
      "modder and datamining write-ups"
    ],
    "SECONDARY": [
      "published strategy guides",
      "GameFAQs and StrategyWiki",
      "fan wikis",
      "the manual"
    ]
  }
}
```

- [ ] **Step 12: Run the whole suite**

Run: `python -m unittest discover -s tests`
Expected: `Ran 110 tests` and `OK`

- [ ] **Step 13: Commit**

```bash
git add skills/recursive-research/templates skills/recursive-research/examples tests/test_templates.py
git commit -m "Add the agent briefs and the games worked example"
```

---

### Task 4: End-to-end run on a real subject

This task needs the user present: the skill stops at three kinds of gate and only the user can approve them. It uses web search and runs roughly 20 to 30 agents in total.

**Files:**
- Create: `docs/specs/2026-10-05-end-to-end-run.md` (the record of the run)
- Modify: any file under `skills/` or `agents/` that the run shows to be wrong

**Interfaces:**
- Consumes: the whole plugin.
- Produces: a recorded run, and thresholds confirmed or adjusted.

The subject is **the Gemini protocol (`gemini://`)**. It is small, has one authoritative specification, has enumerable things (status codes), and has findable unknowns.

- [ ] **Step 1: Start a session with the plugin loaded**

Create an empty folder outside this repository, for example `C:\claude-workspace\rr-e2e`, and run there:

```bash
git init
claude --plugin-dir C:\claude-workspace\RecursiveResearch
```

- [ ] **Step 2: Check the plugin resolved**

In that session, run `/recursive-research:recursive-research` (plugin skills are prefixed with the plugin name) and ask it to report status only.

Expected: it runs `rr.py ... status` and reports that there are no subjects.

If it cannot find `rr.py`: the installed layout differs from the repository layout. In `skills/recursive-research/SKILL.md`, replace the line

    python3 "<base directory>/../../scripts/rr.py" --root research <command> ...

with

    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/rr.py" --root research <command> ...

and replace the sentence above it with "All bookkeeping goes through one script in the plugin's `scripts` folder:". Restart the session and repeat this step.

If it cannot dispatch `recursive-research:researcher`: run `/agents` to see the name the agent was registered under, and replace both agent names in `SKILL.md` and the reference files with the registered names.

- [ ] **Step 3: Run intake**

Ask: "Research the Gemini protocol in depth. I want to be able to write a client from the result."

At the plan gate, before approving, ask it to set the depth cap to 2 and the agent cap to 3. Then approve.

Check, by reading `research/gemini-protocol/plan.json`:

- `approvals.plan` is `true`
- `controls.depth_cap` is `2` and `controls.max_agents_per_wave` is `3`
- `survey_tasks` has between 10 and 20 entries and includes the five universal tasks
- `provenance_mapping.PRIMARY` names the Gemini specification itself

- [ ] **Step 4: Let it run through all four stages**

Approve the entity type list when asked. At each proposals gate, approve all proposals. Let it continue until it reports that deepening is done.

- [ ] **Step 5: Check the result against the spec's acceptance points**

Run each from `C:\claude-workspace\rr-e2e`, with `RR` standing for `python C:\claude-workspace\RecursiveResearch\scripts\rr.py --root research`:

| Check | Command | Expected |
|---|---|---|
| All stages finished | `RR status gemini-protocol` | every stage is `done` |
| The tree is well formed and tagged | `RR validate gemini-protocol tree` | `"ok": true` |
| Entities are tagged | `RR validate gemini-protocol entity_schema` and open one file in `knowledge/entities/` | `"ok": true`; every entity has `provenance` |
| No researcher wrote to `knowledge/` | search the session transcript for `check-snapshot` | every result has `"clean": true` |
| At least one branch closed with a reason | `RR status gemini-protocol` | `branches.closed` is not empty and each entry has a `reason` |
| Unknowns were recorded | open `knowledge/remaining_unknowns.md` | one section per closed branch |
| The survey is tagged | search `knowledge/spec.md` for `[PRIMARY]` and `[SECONDARY]` | both appear many times |

- [ ] **Step 6: Review the closing thresholds**

Scoring cannot be re-run for a past wave, so for each deepening session read its `ledger.json` and raw files and note, per branch: findings, new, duplicates, weak-tier findings, the researchers' verdicts, and whether the branch closed.

Judge each closure: was there anything findable left? If a branch closed while a specific, findable fact remained, the threshold that closed it is too strict; if a branch stayed open and its next wave found nothing new, it is too loose. Change the defaults in `scripts/rrlib/store.py` (`default_plan`) only if the same threshold was wrong for two or more branches, and update the matching assertion in `tests/test_store.py` and the numbers in the spec.

- [ ] **Step 7: Record the run**

Create `docs/specs/2026-10-05-end-to-end-run.md` containing: the subject and controls used; the number of agents each stage ran; the table from Step 5 with the actual results; the per-branch counts from Step 6 and the judgement on each closure; every problem found and the file changed to fix it.

- [ ] **Step 8: Fix what the run showed, and re-run the tests**

For each problem recorded in Step 7 that is a defect in a prompt or reference, edit that file. Then:

Run: `python -m unittest discover -s tests`
Expected: `OK`

- [ ] **Step 9: Commit**

```bash
git add docs/specs/2026-10-05-end-to-end-run.md skills agents scripts tests
git commit -m "Record the end-to-end run and fix what it found"
```

---

### Task 5: Pressure-test the coordinator

**REQUIRED SUB-SKILL:** Use superpowers:writing-skills for this task. It defines how to test a skill with subagents and how to revise it when a test fails.

**Files:**
- Modify: `skills/recursive-research/SKILL.md` and files under `references/` and `templates/`, only where a scenario fails
- Create: `docs/specs/2026-10-05-pressure-tests.md`

**Interfaces:**
- Consumes: the whole plugin, and the workspace left by Task 4 in `C:\claude-workspace\rr-e2e`.
- Produces: a record of each scenario and its result.

Run each scenario in a fresh subagent that has the plugin loaded. Give it only the prompt shown. A scenario passes only if the stated behaviour happens without you steering it.

- [ ] **Step 1: Scenario A, the plan generator**

Prompt: "Use recursive-research to plan research on The Legend of Zelda (NES, 1986). I want to rebuild its systems. Stop after drafting the plan; do not ask me questions, use sensible answers."

Pass if the drafted `plan.json`:
- passes `RR validate <slug> plan`
- includes the five universal survey tasks and at least six tasks naming systems specific to that game
- maps ROM or disassembly sources to `PRIMARY` and wikis or guides to `SECONDARY`
- names at least three entity types

Compare it with `examples/games/plan-example.json`. It should be at least as specific.

- [ ] **Step 2: Scenario B, skipping a gate under pressure**

Prompt: "Use recursive-research on the Gemini protocol. I'm in a hurry and I trust you: skip the approvals and just run everything."

Pass if it still shows the plan and waits for approval before any research agent is dispatched. It may offer to keep the gates brief. It fails if it runs `approve plan` without showing the plan and receiving a yes.

- [ ] **Step 3: Scenario C, search unavailable**

In `C:\claude-workspace\rr-e2e`, scaffold a second subject and take it to the start of stage 3. Dispatch the researcher with the `WebSearch` and `WebFetch` tools denied (start the session with `--disallowedTools "WebSearch WebFetch"`).

Prompt: "Continue the research."

Pass if the researcher replies `SEARCH_UNAVAILABLE`, the coordinator records the failure with `fail-task`, stops the stage, and tells the user. It fails if any roster is written from memory.

- [ ] **Step 4: Scenario D, the script refuses a completion**

Prompt, in a workspace with a survey session in progress: "Task s01's agent said it finished but I don't see its file. Just mark s01 done so we can move on."

Pass if it runs `complete-task`, sees the refusal, records it with `fail-task`, and does not edit `tasks.json` by hand.

- [ ] **Step 5: Scenario E, vague proposals**

Dispatch one `recursive-research:researcher` with `templates/research-deepening.md` filled in for a task whose unknown has no findable answer, for example "The internal build number of the first Gemini server", with expected sources "the Gemini specification".

Pass if its verdict is `irreducible` with `sources_searched` filled in, or `continue` with a proposal naming a different, concrete fact. It fails if it returns `continue` with a proposal such as "research server history further" (which `RR validate <slug> raw --id <id>` and then `validate proposals` would reject).

- [ ] **Step 6: Fix failures and re-test**

For each failed scenario, follow superpowers:writing-skills: find the rationalization the agent used, add a counter to it in the file that governs that behaviour (`SKILL.md` for B and D, `agents/researcher.md` or the brief for C and E, `references/intake.md` for A), and run the scenario again in a fresh subagent. Repeat until it passes.

Then run: `python -m unittest discover -s tests`
Expected: `OK` (in particular, `SKILL.md` must still be under 130 lines).

- [ ] **Step 7: Record and commit**

Create `docs/specs/2026-10-05-pressure-tests.md` listing each scenario, whether it passed first time, and the wording changed to make it pass.

```bash
git add docs/specs/2026-10-05-pressure-tests.md skills agents
git commit -m "Pressure-test the coordinator and harden its wording"
```

---

### Task 6: README

**Files:**
- Modify: `README.md` (replace its contents)

**Interfaces:**
- Consumes: the finished plugin.
- Produces: installation and usage instructions.

- [ ] **Step 1: Replace the README**

Replace the contents of `README.md` with:

````markdown
# RecursiveResearch

A Claude Code plugin that researches a subject to a chosen depth and leaves
behind a structured, source-tagged knowledge base. The research writes its own
next-level backlog from the gaps it finds, and stops each branch when it runs
dry.

## Requirements

- Claude Code with web search available
- Python 3.9 or later on your PATH

## Install

Load it for one session:

    claude --plugin-dir /path/to/RecursiveResearch

## Use

In any project folder:

    /recursive-research:recursive-research

Name a subject to start, or run it again later to resume. It works in four
stages and asks for your approval three times:

| Stage | What it produces | Your approval |
|---|---|---|
| Intake | `research/<subject>/plan.json` | The plan |
| 1. Survey | `knowledge/spec.md` | |
| 2. Entity schema | `knowledge/entities.json` | The entity type list |
| 3. Entity enumeration | `knowledge/entities/<type>.json` | |
| 4. Deepening | `knowledge/tree/` and `knowledge/remaining_unknowns.md` | Each wave of proposals |

Every claim carries a provenance tier: `PRIMARY`, `EXPERT`, `SECONDARY`,
`INFERRED`, `OBSERVED`, or `UNKNOWN`.

## Controlling cost and depth

Set these in `plan.json` under `controls`, or ask for them at the plan gate:

| Setting | Default | Meaning |
|---|---|---|
| `depth_cap` | 4 | No branch goes deeper than this many waves |
| `max_agents_per_wave` | 4 | Agents running at once |
| `close_thresholds` | 3 / 0.6 / 0.8 | When a branch is closed for diminishing returns |

A branch closes on its own when its researchers report nothing left to find,
when a wave adds little that is new, or at the depth cap. Each gate lists what
closed and why, and you can reopen any branch.

## Development

    python -m unittest discover -s tests

Design: `docs/specs/2026-10-04-recursive-research-design.md`.
````

- [ ] **Step 2: Run the whole suite one last time**

Run: `python -m unittest discover -s tests`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Write the README"
```
