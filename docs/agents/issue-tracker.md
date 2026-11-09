# Issue tracker: Local Markdown

Issues and specs for this repo live as Markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`.
- The spec is `.scratch/<feature-slug>/spec.md`.
- Implementation issues are separate files at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`.
- Record triage state in a `Status:` line near the top of each issue. Use the names in `triage-labels.md`.
- Append comments under a `## Comments` heading.

## Skill operations

- To publish an issue or spec, create the appropriate file under `.scratch/<feature-slug>/`.
- To fetch a ticket, read its referenced file.

## Wayfinding operations

- Map: `.scratch/<effort>/map.md`, containing Notes, Decisions-so-far, and Fog.
- Child ticket: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`. Record `Type: research|prototype|grilling|task` and `Status: claimed|resolved`.
- Blocking: record `Blocked by: NN, NN` near the top. A ticket is unblocked when every listed ticket is resolved.
- Frontier: scan open, unblocked, unclaimed tickets in number order.
- Claim: set `Status: claimed` before starting work.
- Resolve: append the answer under `## Answer`, set `Status: resolved`, and add a context pointer to the map's Decisions-so-far.
