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

## 3. Leave the listing to the script

Do not edit `{{WORKSPACE}}/knowledge/remaining_unknowns.md`, and do not list
unknowns or conflicts in your reply. A script collects both after you finish.
Leave every line marked `CONFLICT` exactly as it is.
