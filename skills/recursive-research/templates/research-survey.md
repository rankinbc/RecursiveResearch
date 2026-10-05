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

**How you read a source limits its tier.** The web tools return a summary
written by a model, not the page's own text. A claim you learned only through
a web fetch or a search result is at most `SECONDARY`, even when the page is
the specification itself. `PRIMARY` is only for text you read directly: a
local file you opened, or a passage you can copy word for word from what the
tool returned. When you are not sure the words are the source's own, use the
lower tier.

End the section with a `### Open questions` list of specific facts you could
not find.
