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
