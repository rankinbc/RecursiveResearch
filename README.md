# RecursiveResearch

**A Claude skill for deep research**, packaged as a plugin for
[Claude Code](https://claude.com/claude-code).

You name a subject. Claude researches it to a chosen depth and leaves behind a
structured, source-tagged knowledge base. The research writes its own
next-level backlog from the gaps it finds, and stops each branch when it runs
dry.

It is not a standalone program: it runs inside Claude Code, which supplies the
model, the agents and the web search. The repository holds the skill (the
instructions Claude follows), two agent definitions, and a small Python script
that keeps the state.

## Requirements

- Claude Code with web search available
- Python 3.9 or later on your PATH

## Install

The repository is its own plugin marketplace. Inside Claude Code:

    /plugin marketplace add rankinbc/RecursiveResearch
    /plugin install recursive-research@recursive-research

From a local clone, give the folder path in place of `rankinbc/RecursiveResearch`.

To try it for one session without installing:

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

## Watching a run

From a second terminal in the same project folder:

    python /path/to/RecursiveResearch/scripts/rr.py --root research progress <subject> --watch

It refreshes every 5 seconds and shows task counts per stage, which tasks are
running, done or blocked, findings per wave, and which branches are open or
closed and why. A task shows as running from when it is handed to an agent
until it completes or fails; there is no view inside an agent while it works.

## Controlling cost and depth

Set these in `plan.json` under `controls`, or ask for them at the plan gate:

| Setting | Default | Meaning |
|---|---|---|
| `depth_cap` | 4 | No branch goes deeper than this many waves |
| `max_agents_per_wave` | 4 | Agents running at once |
| `close_thresholds` | 3 / 0.6 / 0.8 | When a branch is closed for diminishing returns |

A branch closes on its own when:

- its researchers report nothing left to find, or nothing findable, or
  nothing that matters for your goal;
- a wave added fewer than 3 new facts and resolved no unknowns;
- more than 60% of a wave's findings were duplicates;
- a wave resolved nothing and more than 80% of its findings were inferred or
  observed;
- it reaches the depth cap.

Each gate lists what closed and why, and you can reopen any branch.

## How far to trust the tiers

Web tools return a model's summary of a page, not its text, so a researcher
can "quote" a sentence the page never contained. Two things guard against that:

- **In stage 4 the script checks every `PRIMARY` quote itself.** It opens the
  cited page and looks for the quoted words. A finding whose quote is there is
  marked verified. One whose quote is missing, or whose source cannot be
  opened, is downgraded to `SECONDARY` with the reason recorded. On the first
  real wave it confirmed 22 of 26 quotes and downgraded 4: three that were not
  in the page they cited, one of them a disputed fact, and one too short to
  check.
- **In the survey and entity rosters there is no such check.** Researchers are
  told to cap anything they read only through a web tool at `SECONDARY`, but
  nothing enforces it. Treat `PRIMARY` there with more caution.

Before relying on an exact limit or wording, read the source yourself.

## Status

Version 0.1.0, a pre-release. What has and has not been checked:

- **Tests.** The bookkeeping script has a unit test suite that runs on
  Windows, macOS and Linux, on Python 3.9 and 3.13, on every push.
- **Installing.** Adding the marketplace and installing from it was checked
  from this GitHub repository, on Windows.
- **A real run.** One subject has been taken through all four stages and one
  research wave, on Windows. See `docs/end-to-end-run.md`.
- **Holding its rules.** Four pressure scenarios pass, one of them only after
  a fix. See `docs/pressure-tests.md`.

Not yet shown:

- The diminishing-returns thresholds have never fired in a real run. Treat the
  defaults as guesses and expect to tune them.
- No run has gone two waves deep.
- The quote check was verified against saved results, not during a live wave.
- No research has been run on macOS or Linux.

## Development

    python -m unittest discover -s tests

Design, and what changed while building it:
`docs/specs/2026-10-04-recursive-research-design.md`.

## License

MIT. See `LICENSE`.
