# ADR-0006: Remove shipped build plans rather than archiving them in-tree

- **Status:** Accepted
- **Date:** 2026-09-01
- **Affects:** `docs/superpowers/` (removed); agent context budget
- **Related:** [ADR-0001](0001-record-architecture-decisions.md)

## Context

`docs/superpowers/` held 9 documents — 5 plans and 4 specs, 1,749 lines total — written between
2026-05-27 and 2026-07-01 as build plans for work that has since shipped: the Phase 2 firmware,
the live acquisition path, the Windows tree ERT UI, control-drift mode, and the Phase 3A hybrid
debug UI. Each was verified against the tree before removal; the corresponding code exists.

These are *forward-looking* documents describing intended work. Once the work lands, they
describe the past in the future tense, which is worse than describing nothing — an agent
reading a plan cannot tell whether it is a specification of current behaviour, a proposal, or a
historical artifact. The only inbound references were four dead links from `PROJECT_CONTEXT.md`,
itself stale and pointing at a directory path that is not this repository.

The repo carries roughly 8,000 lines of markdown against a much smaller body of code. Every
stale document competes for agent attention with the documents that are actually authoritative
(`AGENTS.md`, `CLAUDE.md`, `docs/validity-audit.md`).

## Decision

Delete `docs/superpowers/` outright. Git history is the archive; the documents are recoverable
with `git log --diff-filter=D -- docs/superpowers/` and `git show <commit>^:<path>`.

## Rationale

The obvious alternative was moving them to `docs/archive/`. Rejected because an archive
directory inside the working tree still gets read — by grep, by file-tree listings, and by
agents doing repository surveys. It converts a "stale document" problem into a "stale document
with a disclaimer" problem, and the disclaimer is only load-bearing if every reader notices it.

Git already provides exactly the semantics wanted: content retained, retrieval possible,
zero cost to anyone not specifically looking for it. Keeping a second archive inside the tree
duplicates that at the cost of the thing being optimised for.

The provenance concern raised when this cleanup was first proposed — that thesis work might
need to show how the build was planned — is satisfied by history. If a written record of
planning method becomes necessary for the thesis, it should be written deliberately for that
purpose, not assembled from stale agent plans that were never intended as a narrative.

Alternatives rejected:

- **Keep them, add a "historical" header to each.** Nine headers, each relying on being read.
- **Move to `docs/archive/`.** Discussed above; still in the tree, still surfaces in searches.

## Consequences

Anyone wanting the original plans must know to look in git history — this ADR is the pointer,
and is the reason it exists rather than being a silent deletion.

`PROJECT_CONTEXT.md` now has four dead links. That file was already identified as the most
stale document in the repository (it describes the project as Phase 1/Phase 2 and points at
`C:/Users/Vidad/Documents/ERT/`) and is a separate pending cleanup; this ADR does not address it.

The precedent set is that shipped forward-looking documents get deleted, not archived. Applying
this consistently means `PHASE_3_12_ELECTRODE_PLAN.md` (962 lines, hardware now built) is a
candidate for the same treatment.

## Verification

`docs/superpowers/` no longer exists. `git log --diff-filter=D -- docs/superpowers/` returns the
removing commit, and the contents are retrievable from its parent. Each plan's shipped artifact
was confirmed present before removal: `tree_ert/ui.py`, `tree_ert/controller.py`,
`phase3a_unified_reconstruct.py` (`analyze_control_drift`, `tune_drift`), and both firmware
generations.
