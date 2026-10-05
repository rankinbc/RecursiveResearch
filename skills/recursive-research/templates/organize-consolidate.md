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
