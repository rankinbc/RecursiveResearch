# RecursiveResearch

**A Claude skill for deep research**, packaged as a plugin for
[Claude Code](https://claude.com/claude-code).

Name a subject. Claude researches it in depth and leaves you a structured
knowledge base in your project folder. Every claim says how well it is
supported, and the top-tier findings in the deep layer are checked against
their source.

    /plugin marketplace add rankinbc/RecursiveResearch
    /plugin install recursive-research@recursive-research

## Why use it

Asking a model to "research X" gives you one long answer you have to take on
trust. This gives you something you can build on:

- **Depth that follows the gaps.** Each round of research ends by listing the
  specific facts still missing. Those become the next round's tasks, so effort
  goes where the unknowns are instead of being spread evenly.
- **It knows when to stop.** Every branch of the subject closes on its own
  when there is nothing left to find, nothing findable, or nothing that
  matters for your goal. You are not paying for research that has run dry.
- **Every claim is graded.** Six tiers, from `PRIMARY` (the source itself)
  down to `UNKNOWN`. A missing value is recorded as missing rather than guessed.
- **Quotes are verified.** In the deepening stage, the script opens each
  cited page itself and looks for the quoted words. A quote that is not there
  loses its top tier, with the reason recorded.
- **You stay in control of cost.** You approve the plan, the list of things to
  catalogue, and each round of deeper research, and each approval tells you
  how many agents it will run.
- **It survives interruption.** Everything is on disk. Close the session and
  pick up later, or watch progress live from another terminal.

## How it works

You give it a subject and say what the research is for. It then works through
four stages:

| Stage | What happens | What you get |
|---|---|---|
| **Plan** | Claude asks a few questions and drafts a research plan for your subject. **You approve it.** | `plan.json` |
| **1. Survey** | One researcher per topic, in parallel, writes a broad overview. | `knowledge/spec.md` |
| **2. Schema** | Claude identifies the kinds of thing your subject has many of, and their properties. **You approve the list.** | `knowledge/entities.json` |
| **3. Catalogue** | One researcher per kind lists every instance, with a tier on every value. | `knowledge/entities/*.json` |
| **4. Deepening** | Rounds of targeted research, each resolving specific unknowns and proposing the next. **You approve each round.** | `knowledge/tree/` |

Two kinds of agent do the work, and they are kept apart on purpose:

- **Researchers** find things. They search, read, and write raw findings.
  They never touch the knowledge base.
- **Organizers** file things. They place findings in the right branch, remove
  duplicates, and settle conflicts by tier. They have no search tools: their
  job is to file what was found, not to add to it.

A small Python script keeps all the state and enforces the rules: no research
before the plan is approved, stages in order, and no task marked done without
valid output.

### The deepening loop

This is the part that gives the plugin its name.

    known unknowns ──▶ you approve ──▶ researchers ──▶ organizer
          ▲                                                │
          │                                                ▼
          └──── new proposals ◀── branches scored ◀── findings filed

Each researcher finishes with a verdict:

| Verdict | Meaning |
|---|---|
| `exhausted` | The question is answered and nothing new is worth asking. |
| `irreducible` | Something is still unknown, but the sources do not hold the answer. |
| `sufficient` | Something is still unknown, but it does not matter for your goal. |
| `continue` | A specific further fact is findable. It must be named. |

"Research this further" is rejected. A follow-up has to name one concrete
missing fact and where it might be found.

A branch closes when its researchers stop asking for more, when a round adds
little that is new, or when it reaches the depth you set. Each approval point
lists what closed and why, and you can reopen any branch.

## What you end up with

    research/<subject>/
      plan.json                  the approved plan
      knowledge/
        spec.md                  the survey: a readable overview
        entities.json            what kinds of thing exist
        entities/                every instance of each kind
        tree/                    the deep knowledge, branch by branch
        remaining_unknowns.md    what was not found, and why

The tree goes from overview to exact detail. Each folder has a README that
summarizes its level, links deeper, and ends with a checklist of what is still
unknown. The leaves hold exact values, formulas and algorithms.

Claims are tagged where they stand:

    The header is 12 bytes [PRIMARY]. Retries are capped at about five [OBSERVED].
    The backoff multiplier is not documented [UNKNOWN: est 1.5-2].

| Tier | Meaning |
|---|---|
| `PRIMARY` | The thing itself: source code, the original document, raw data |
| `EXPERT` | Verified by practitioners with direct access |
| `SECONDARY` | Published guides, references, wikis |
| `INFERRED` | Derived from other tagged facts |
| `OBSERVED` | Seen but not confirmed |
| `UNKNOWN` | Needed but not found |

When two sources disagree, the stronger tier wins. When they are equal, both
are kept and the line is marked `CONFLICT` for you to decide.

### An example

Asked to research the Gemini protocol well enough to write a client, it
produced a 15-section survey, a catalogue of 126 instances across 11 kinds of
thing (status codes, line types, MIME parameters and so on), and a tree of 8
branches with 18 proposals for deeper work. One round of four researchers
returned 65 findings. The organizer filed 33 as new and set aside 30 as
duplicates, and two disputes left over from the survey were settled by tier.
Run over that round's 26 top-tier quotes, the script's source check confirmed
22 and downgraded 4.

The full account is in [`docs/end-to-end-run.md`](docs/end-to-end-run.md).

## Using it

**Requirements:** Claude Code with web search, and Python 3.9 or later.

**Install**, inside Claude Code:

    /plugin marketplace add rankinbc/RecursiveResearch
    /plugin install recursive-research@recursive-research

**Run it** in any project folder:

    /recursive-research:recursive-research

Then say what you want researched and what it is for, for example:

> Research the Gemini protocol. I want to be able to write a client from the
> result.

What it is for matters. Claude uses it to decide which unknowns are worth
chasing and when a branch is done.

Run the same command again later to resume, or to ask where a project stands.

**To try it without installing**, from a clone:

    claude --plugin-dir /path/to/RecursiveResearch

### Watching a run

From a second terminal in the same folder:

    python /path/to/RecursiveResearch/scripts/rr.py --root research progress <subject> --watch

It shows something like this, refreshed every few seconds:

    Gemini protocol  (research/gemini-protocol)
    Next: Dispatch the next batch of tasks in 2026-10-05_deepening_w01 (next-task).

    Stages
      done         survey               16/16
      done         entity_schema        1/1
      done         entity_enumeration   11/11
      in progress  deepening            3/5

    Current session: 2026-10-05_deepening_w01
      done     frame-max-length         Find the maximum frame length  (irreducible)
      done     status-codes             Wording for each status code  (continue)
      running  tls-requirements         TLS version and SNI requirements
      blocked  redirect-limit           The redirect counting rule  -- search timed out

    Waves
      wave  tasks   findings  new   dup   conflict  resolved  opened  scored
      w01   2/4     6         -     -     -         2         0       no

### Controlling depth and cost

Ask for these when you approve the plan, or set them in `plan.json`:

| Setting | Default | Meaning |
|---|---|---|
| `depth_cap` | 4 | No branch goes deeper than this many rounds |
| `max_agents_per_wave` | 4 | Agents running at once |
| `close_thresholds` | 3 / 0.6 / 0.8 | When a branch counts as run dry |

A branch closes on its own when:

- its researchers report nothing left to find, nothing findable, or nothing
  that matters for your goal;
- a round added fewer than 3 new facts and resolved no unknowns;
- more than 60% of a round's findings were duplicates;
- a round resolved nothing and more than 80% of its findings were inferred or
  observed;
- it reaches the depth cap.

Each approval point is also a safe place to start a fresh session, which keeps
long runs cheap.

## Which claims to lean on

The tree is the verified layer. A `PRIMARY` finding there carries the exact
quote and its address, and the script has opened that address and found the
words. Findings it could not confirm are marked as such, with the reason.

The survey and the catalogue are the map that gets you there. Their tiers are
assigned by the researchers under the same rules, without the script's check.
Use them to find your way, and use the tree for anything exact.

## What is in the repository

This is a skill, not a standalone program. It runs inside Claude Code, which
supplies the model, the agents and the web search.

| Path | What it is |
|---|---|
| `skills/recursive-research/` | The skill: the coordinator's instructions, one reference per stage, and the briefs agents receive |
| `agents/` | The researcher and organizer definitions |
| `scripts/rr.py` | The bookkeeping script. Standard library only, nothing to install |
| `tests/` | The script's test suite |
| `docs/` | The design, the first end-to-end run, and the pressure tests |

## Development

    python -m unittest discover -s tests

The tests run on Windows, macOS and Linux, on Python 3.9 and 3.13, on every
push.

- Design: [`docs/specs/2026-10-04-recursive-research-design.md`](docs/specs/2026-10-04-recursive-research-design.md)
- First real run: [`docs/end-to-end-run.md`](docs/end-to-end-run.md)
- Pressure tests: [`docs/pressure-tests.md`](docs/pressure-tests.md)

## License

MIT. See `LICENSE`.
