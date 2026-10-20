# ADR-0067: Proceed to the disc-06 drilled-defect test with E1/E2 excluded

- **Status:** Accepted
- **Date:** 2026-10-20
- **Affects:** disc-06 capture plan (drilled defect in the E5-E7 sector), every absolute image
  from this ADR on (`absolute_exclude_electrodes = (1, 2)`), thesis claims about angular coverage
- **Related:** ADR-0064 (exclusion mechanism), ADR-0066 (residual E10-E12 leak, ~300 µA floor),
  `docs/handoff-2026-10-19/README.md` §3.1 step 3 (which this ADR overrides)

## Context

The 2026-10-19 handoff made the E1/E2 board-channel fault blocking: no specimen work until saline
with **all** electrodes reaches misfit ≤15 %. After the 2026-10-20 board clean (ADR-0066) it still
does not. Re-solving the 2026-10-20 empty-saline runs offline (`absolute.evaluate`, dac 400,
settle 10, 16 samples):

| Run | all electrodes | E1, E2 excluded |
|---|---|---|
| 20261020-150548 (all electrodes) | 60.3 % FAIL | 11.4 % PASS |
| 20261020-151203 (all electrodes) | 60.4 % FAIL | 11.0 % PASS |
| 20261020-152105 (clip swap) | 81.3 % FAIL | 61.8 % FAIL |
| 20261020-152722 (terminal-block swap) | 81.0 % FAIL | 61.0 % FAIL |
| 20261020-154712 (first Raspberry Pi 5 host run) | 63.9 % FAIL | 13.5 % PASS |

With normal wiring, the exclusion passes all three runs, at 11.0-13.5 %. The swap runs fail
even with it, because their wiring is no longer in the electrode map the solve assumes.
They are kept as fault-location evidence, not as images. The contact check still flags E1 and E2
(and sometimes E3) on every run.

## Decision

Accept the E1/E2 fault as a known limitation and start the disc-06 drilled-defect test now, with
`absolute_exclude_electrodes = (1, 2)` on every absolute solve. The hole is drilled in the E5-E7
sector, where all sensing electrodes are live. The E1-E3 sector is declared blind, and the thesis
states it.

## Rationale

- **Fix the board first (the handoff's order).** This is still the right fix: inspect the E1/E2
  mux pins, or move the wires to spare mux channels 12-15. It was rejected for now on schedule.
  With the exclusion in place, the saline fit passes the gates (11.0-13.5 %), so the board fix
  limits coverage, not validity.
- **Defect sector.** E5-E7 is opposite the excluded pair and clear of the ADR-0066 leak at
  E10-E12. disc-05 showed what happens otherwise: its hole sat between E1 and E2 and could not be
  tested.
- **disc-06** passed 6/6 absolute with all electrodes on 2026-10-19 (misfit ≈4 %, reciprocity
  ≈1 %), so intact reference scans of this disc already exist. That gives a before/after pair on
  the same specimen, not a cross-specimen baseline (ADR-0046).

## Consequences

- **Thesis wording.** Coverage claims must name the gap: "E1-E3 sector not imaged (ADR-0064,
  ADR-0067)". A defect in that sector is undetectable by construction, and a quiet image there is
  not evidence of sound wood.
- **Intact scan first.** Scan disc-06 intact, with the same exclusion, before drilling.
  2026-10-19 scans used all electrodes, so they cannot serve as the reference for an excluded solve.
- **Current floor.** ADR-0066 still applies. If disc-06 drives under ~300 µA, the E10-E12 leak is
  more than 3 % of the reading, and the run is noted as below the floor.
- **Difference images are unaffected.** They do not use the exclusion. E1/E2 artefacts can still
  show there and must be read with ADR-0064 in mind.
- **Gates still apply.** ADR-0041 gates (reciprocity ≤15 %, misfit ≤15 %, significance ≥2.0) are
  unchanged. The passes above are only 1.5-4 points under the misfit gate.

## Verification

- Re-solve: load each run above with `tree_ert.survey.load_frames` and pass it to
  `tree_ert.absolute.evaluate` with `absolute_exclude_electrodes=(1, 2)`. The figures in the
  table should reproduce.
- Every disc-06 run's figure caption and log carry `EXCLUDED E1 E2: 56/108 pairs` (ADR-0064).
- Falsified if the intact disc-06 scan with the exclusion fails the misfit gate, or if the drilled
  hole does not appear in the E5-E7 sector against the intact disc-06 scan.
- Superseded once saline with all electrodes passes ≤15 % misfit after a board fix.
