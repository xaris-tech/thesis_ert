# Architecture Decision Records

Every non-obvious decision in this project gets a record here — firmware, host tooling,
measurement methodology, and thesis-facing claims alike.

## Why this exists

This is a research prototype where the hardware, the reconstruction maths, and the thesis
narrative constrain each other. A change that looks like a small code edit ("substitute the
baseline value for a bad pair") can silently change what an image *means*. Six months later,
neither the author nor a thesis panel can reconstruct why a threshold is 10% rather than 5%,
or why a known-imperfect approach was chosen over the textbook one.

An ADR captures the reasoning at the moment it was still fresh, including the options that were
rejected. It is the difference between "the code does X" and "we know why the code does X."

## When to write one

Write an ADR when a decision:

- changes what a reconstruction image means, or how it must be read
- picks a threshold, constant, or tolerance whose value is a judgement call
- rejects a more obvious approach for a non-obvious reason
- accepts a known limitation instead of fixing it
- changes the serial protocol, the capture procedure, or the measurement methodology
- affects a claim the thesis makes about what the instrument can do

Do **not** write one for: routine refactors, typo fixes, test additions that don't change
behaviour, or dependency bumps.

If unsure — write it. A short ADR that turns out to be obvious costs five minutes. A missing
one costs a re-derivation.

## How to write one

1. Copy `template.md` to `NNNN-short-kebab-title.md`, taking the next free number.
2. Fill it in. Keep it short — most ADRs fit on one screen.
3. Status starts as `Proposed` or `Accepted`. Never edit a decision after it's accepted:
   supersede it with a new ADR and mark the old one `Superseded by ADR-NNNN`.
4. Link related records with `Supersedes` / `Superseded by` / `Related`.
5. Reference the ADR number in the commit message that implements it.

## Relationship to other docs

- `docs/validity-audit.md` — records *defects found* and their fix status. An ADR records
  *why a fix was done a particular way*. The audit's D-05 entry says the row-dropping fix
  landed; ADR-0002 says why it masks rows instead of rebuilding the Jacobian.
- `docs/planned-improvements.md` — the work queue. An item there becomes an ADR when the
  approach is decided, not when the item is filed.
- `AGENTS.md` / `CLAUDE.md` — standing rules and domain truths. Those describe the current
  state; ADRs describe how it got there.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-exclude-untrusted-rows-from-solver.md) | Exclude untrusted rows from the solver rather than substituting baseline values | Accepted |
| [0003](0003-reciprocity-as-report-not-gate.md) | Reciprocity error is reported, not enforced as a capture gate | Accepted |
| [0004](0004-opt-in-pinned-colorbar.md) | Colorbar pinning is opt-in per run set, not the default | Accepted |
| [0005](0005-firmware-tests-stay-text-assertions.md) | Firmware tests stay text assertions; the limitation is documented, not engineered away | Accepted |
| [0006](0006-remove-shipped-superpowers-plans.md) | Remove shipped build plans rather than archiving them in-tree | Accepted |
