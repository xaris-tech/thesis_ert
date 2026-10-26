# ADR-0070: Solve with no electrodes excluded first; every exclusion is justified against that solve

- **Status:** Accepted
- **Date:** 2026-10-21
- **Affects:** every absolute solve reported from a recorded run; `absolute_exclude_electrodes`; `docs/handoff-2026-10-19/scripts/saline_matrix.py` usage; thesis figures
- **Related:** ADR-0002 (drop untrusted rows), ADR-0041 (absolute gates), ADR-0064, ADR-0067 (E1/E2 excluded), ADR-0068 (detection criterion)

## Context

Since ADR-0067 every capture has been solved with E1/E2 excluded by default, and the
capture script prints only that solve. On 2026-10-21 that default hid what the data said:

- disc-02 baseline `20261021-144429`: no exclusion 54.6 % misfit, E1 only 19.2 %, **E2 only
  7.7 % (pass, 72 pairs)**, E1+E2 7.5 % (56 pairs). The fault on this disc is E2 alone, and the
  default threw away 16 pairs and blinded E1–E3 for nothing.
- disc-05 `20261021-145855` (holes at E12, E1–E3): the default blinded exactly the sector the
  holes are in; E2-only kept it.
- disc-08 `20261021-155233`, `160701`, `162917`: misfit 29–35 % with E1/E2 excluded; a
  leave-one-out sweep showed **E9** was the outlier (5.5–5.6 % without it), through three nail
  placements. The default exclusion would never have pointed at E9.

The operator asked that this be written down: an exclusion is a conclusion drawn from the
data, so the data has to be looked at without it first.

## Decision

For every recorded run that is reported:

1. Solve with **no electrodes excluded** first and report its misfit, reciprocity and verdict,
   even when it is refused.
2. Then a **leave-one-out sweep** (each electrode excluded alone, and on top of any standing
   exclusion) to find which electrode, if any, carries the misfit.
3. Exclude only the electrodes that sweep points at, and state in the report: the unexcluded
   result, the excluded set, the reason (sweep result, contact flag, known fault ADR), the pairs
   kept and the sector made blind.

A standing exclusion such as ADR-0067's E1/E2 is a hypothesis to be rechecked on each run, not
a setting that replaces step 1.

## Rationale

- **Default exclusion only** (status quo) was rejected: it reports a pass while hiding which
  electrode is actually bad, discards good pairs, and can blind the sector under test.
- **Never exclude** was rejected: the E1/E2 mux fault (ADR-0064) is real, and all-electrode
  solves refuse at 55–96 % misfit.
- Solving first, then excluding with a stated reason, keeps exclusion an evidence-based step
  and makes every image traceable to the measurement as captured. Raw frames always hold all
  12 electrodes, so this costs seconds of compute and no bench time.

## Consequences

- Reports get longer: two solves and a sweep per run.
- The excluded set may differ between specimens (disc-02: E2; disc-08: E9 plus the E1/E2
  fault). Images from different exclusions are not directly comparable, so a difference
  (before/after) pair must use the same exclusion on both.
- ADR-0067's E1/E2 default is now in question; whether to change it to E2 only needs the
  empty-tank and disc-06 rechecks and its own ADR.
- `saline_matrix.py` still prints only the excluded solve; until it is changed, the agent runs
  the unexcluded solve and sweep separately (`tree_ert.absolute.evaluate` with
  `absolute_exclude_electrodes=()` and each single electrode).

## Verification

Not enforced by code. Checkable per report: every absolute result cited must state the
unexcluded misfit and the reason for each excluded electrode. Making `saline_matrix.py` (or a
repo CLI) print the unexcluded solve and the sweep would enforce it.
