# First end-to-end run

Date: 2026-10-05
Subject: the Gemini protocol (`gemini://`), researched so that a client could
be written from the result.
Platform: Windows, Python 3.13, plugin loaded with `--plugin-dir`.
Controls: depth cap 2, agent cap 4, default closing thresholds.

This records what the first real run showed. Figures marked *checked* were
read from the workspace files afterwards. Figures marked *reported* come only
from the coordinator's summary.

## What ran

| Stage | Work | Outcome |
|---|---|---|
| Intake | Plan drafted and approved | 15 survey tasks (*checked*) |
| 1. Survey | 15 researchers, then assembly | `spec.md`, 646 tagged claims (*checked*) |
| 2. Entity schema | 1 organizer | 11 entity types (*checked*) |
| 3. Entity enumeration | 11 researchers | 126 instances, 782 tagged values (*checked*; the coordinator's summary said 122 instances) |
| 4. Bootstrap | 1 organizer | 8 branches, 18 proposals (*checked*) |
| 4. Wave 1 | 4 researchers, 1 organizer | 65 findings; 4 branches closed (*checked*) |

All 33 tasks completed on the first attempt (*checked*). The knowledge
snapshot check was clean after every research batch (*reported*).

The run was done in two sittings. The first stopped at the bootstrap gate with
no proposals approved. The second approved 4 of the 18 proposals, the ones
aimed at four conflicts the survey had left, and ran one wave.

## What it confirmed

- The plugin loads and finds its script and agents when installed.
- Briefs render with every placeholder filled.
- The ledger had an entry for each of the 65 findings: 33 new, 30 duplicate,
  2 conflict.
- Scoring closed all four branches as `sufficient`, since no researcher
  proposed further work, and recorded their open unknowns.
- Two of the four conflicts were settled by tier precedence. Out-of-range
  status codes: `PRIMARY` over the survey's `INFERRED`. The 0.16.1 release
  date: `EXPERT` over two `SECONDARY` values.

## What it exposed, and what was changed

**The top tier was inflated.** About half the survey's claims (326 of 646) and
61% of entity values (478 of 782) were tagged `PRIMARY`, though nearly all
were read through a web tool that returns a model's summary of a page.

- The briefs now cap anything read only that way at `SECONDARY`.
- A `PRIMARY` finding in stage 4 must carry a quote and its source address.
- The script fetches that source and checks the quote. Run on wave 1's
  results it confirms 22 of the 26 `PRIMARY` quotes and downgrades 4. Three
  were not in the page they cited, including the sentence saying an empty META
  defaults to `text/gemini`, which is one of the disputed facts. The fourth
  was too short to check.

Wave 1 itself ran before the quote check existed, so its tree still carries
those four findings as `PRIMARY`.

**A parent branch took its sub-branches with it.** Found in a dry run before
the wave: closing a branch dropped the proposals of every branch beneath it.
Branches now close one at a time.

**One fix round could not succeed.** A JSON leaf missing both `_meta` fields
was told about one per round, and the organizer is allowed one fix. The wave
ended with four leaves failing validation. Validation now reports both at
once, and the organizer briefs show the exact block.

**A dropped proposal was not named.** The organizer proposed a follow-up to
settle the header-length conflict, on a branch that then closed. The gate
reported a count only. It now lists each dropped proposal.

**Researchers disagreed about a non-normative document.** Three tagged the
technical overview `PRIMARY` and one `SECONDARY`. Intake now tells the plan to
name authoritative and informal documents separately.

**Python 3.9 did not work.** Continuous integration, not the run, found a
call that needs Python 3.10. Fixed; all six jobs pass.

## Afterwards: the check extended to everything

The quote check was later extended from stage 4 findings to the whole
knowledge base, with evidence required on every `PRIMARY` claim. Run on a copy
of this run's knowledge base, it confirmed 9 claims and downgraded 1,040.

That is the expected result, not a regression. This run was done before
evidence was required, so nearly all of its `PRIMARY` tags had no quote to
check. The 9 that passed were tree entries where the organizer had happened to
keep the quote and address. A run under the current rules has not yet been
done, so the share of claims that survive the check in practice is not known.

## What is still unproven

- **The closing thresholds.** Every branch in the one wave closed on its
  researchers' verdicts, so the diminishing-returns rules never fired. The
  numbers 3, 60% and 80% remain guesses.
- **A second wave.** No branch stayed open, so nothing has gone two levels
  deep.
- **The quote check in a live run.** It was verified against this run's saved
  results, not during a run. Researchers have not yet been asked to supply
  evidence in the survey, the catalogue or the tree, so it is not known how
  well they do it.
- **The report on a large knowledge base.** It was generated from this run's
  1,770 claims (a 450 KB page) and looked at in both themes. Nothing larger
  has been tried.
- **Large waves.** The largest had four tasks. One organizer per wave may not
  hold up at twenty.
- **Other platforms.** The tests pass on macOS and Linux; no research has
  been run there.

## Sources the researchers could not reach

`gemini.circumlunar.space` failed on a certificate error and
`web.archive.org` was unreachable, so the pre-0.24 specification text was not
read directly, and version attributions rest on secondary sources.
