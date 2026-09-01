# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-09-01
- **Affects:** all future work; `CLAUDE.md`, `AGENTS.md`
- **Related:** `docs/validity-audit.md`, `docs/planned-improvements.md`

## Context

This project's decisions span three coupled layers: firmware behaviour, host-side
reconstruction maths, and the claims the thesis makes about what the instrument measures. A
change in any one silently changes the meaning of the others.

The 2026-08-27 validity audit demonstrated the cost of not recording reasoning. Five defects
had survived in the codebase, and in at least two cases (D-01 electrode label mirroring, D-02
global sign inversion) the original intent was no longer recoverable from the code — the audit
had to re-derive it against PyEIT's forward solver to establish which convention was correct.
Sign and orientation conventions are exactly the kind of decision that is obvious while being
made and unrecoverable a month later.

Existing docs cover adjacent ground but not this. `validity-audit.md` records defects and their
fix status. `planned-improvements.md` records a work queue. Neither records *why* a fix took
the shape it did, or which alternatives were rejected.

## Decision

Every non-obvious decision is recorded as a numbered ADR in `docs/adr/`, following
`docs/adr/template.md`. `CLAUDE.md` and `AGENTS.md` instruct agents working in this repo to
write one as part of the change that implements the decision, not afterwards.

## Rationale

Alternatives considered:

- **Commit messages only.** Already in use and already insufficient — they are not indexed, not
  cross-linked, and a reader has to know a decision exists before they can find it.
- **Expand `validity-audit.md`.** That document is a point-in-time independent review with
  evidential value precisely because it is a snapshot. Growing it into a living decision log
  would destroy that property.
- **Inline code comments.** Good for local invariants, and already used for the D-02 sign
  convention. They do not survive refactors and cannot record a rejected alternative.

ADRs are numbered, immutable once accepted, and superseded rather than edited — which means
the reasoning behind a *reverted* decision survives too. For a thesis, that history is itself
defensible evidence of method.

## Consequences

Every substantive change now carries a documentation cost. That is the point, but it will feel
like friction on small changes, and the `README.md` "when to write one" list exists to keep
that bounded.

The index in `docs/adr/README.md` must be updated by hand when an ADR is added; nothing
enforces this automatically. A stale index is the most likely failure mode of this scheme.

## Verification

`docs/adr/` exists with a template and index; `CLAUDE.md` and `AGENTS.md` both instruct agents
to maintain it. Whether the practice actually holds can only be checked by looking at whether
subsequent substantive commits carry ADR numbers.
