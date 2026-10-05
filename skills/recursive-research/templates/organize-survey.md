# Assemble the survey for {{SUBJECT}}

`{{WORKSPACE}}/knowledge/spec.md` has already been assembled by a script: a
title, a contents list, each researcher's section in order, and a list of any
missing sections. Review it and improve it in place.

Do not rewrite the file. Read it once, then make targeted changes with the
Edit tool. Rewriting it risks dropping or altering what the researchers wrote.

## Edits to make

1. Fix inconsistencies between sections. Where two sections give different
   values for the same fact, keep the stronger tier
   (`PRIMARY > EXPERT > SECONDARY > INFERRED > OBSERVED`) and correct the
   other. At the same tier, keep both and mark the line `CONFLICT`.
2. Add cross-references where one section relies on another.
3. Move every section's "Open questions" items into one `## Open questions`
   list placed before "Missing sections" (or at the end), removing repeats.
4. Check that each contents link matches its section heading.

Do not add facts of your own. Do not remove a claim because it is uncertain;
its tag already says so. Keep every provenance tag.

This brief was written for session `{{SESSION}}`.
