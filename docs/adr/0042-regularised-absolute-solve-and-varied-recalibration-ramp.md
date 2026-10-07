# ADR-0042: Regularise the absolute solve, and recalibrate down a varied ramp that stops on contact faults

- **Status:** Accepted
- **Date:** 2026-10-06
- **Affects:** `tree_ert/absolute.py`, `tree_ert/qt/worker.py`, `absolute_session.py`
- **Related:** ADR-0041 (amends its solver and ladder; its gates stand), ADR-0032, ADR-0039

## Context

On 2026-10-06 the first live session ran disc-02 through ADR-0041's recalibration. The instrument was healthy: the resistor ring read 0.1 % reciprocity and 0.11 % noise that morning. Every disc-02 attempt was still refused:

- reciprocity 15-21 %
- model misfit 65-73 %
- a flagged electrode that wandered E1/E2/E5 → E2 → E3 between attempts

Against a homogeneous disc model the data correlated at only 0.2-0.3, compared with 0.88 on the 09-29 dry disc. Dropping the worst electrodes' rows still left 54-66 % misfit.

Reviewing the solver turned up two flaws:

1. **No prior on the solution.** Its damping slowed each step but never pulled the answer back. A healthy disc reached element values 2.6x sigma0, and a wet one 10^5 x.
2. **No step control.** Once a proper prior was added, full Gauss-Newton steps overshot, with log-sigma swinging by about e^20.

The tuning ladder also had problems. It only lengthened settle, its 100 ms steps were near-duplicates, and it would have retried a contact fault for hours: one frame takes 64 s at the preset.

## Decision

- **Solver:** Tikhonov prior on log(sigma/sigma0), weight 0.03 of max diag(J'J) at the homogeneous start. A backtracking line search on the regularised objective. Up to 30 iterations.
- **Ramp:** settle 10 / 30 / 50 / 75 / 100 / 150 / 200 ms. Alongside it, samples 8-32 (the firmware clamps at 32), warmup 5-30, frames 10-16, and DAC stepping from 100 % to 80 % of the starting code. The operator's own settings run first.
- **Contact-fault stop:** recalibration stops after 3 consecutive attempts that each flag a suspect electrode (ADR-0032).
- **Time estimate:** each attempt's estimated duration is logged, at 8.3 ms per sample plus settle, times 216 records.

## Rationale

| Weight | Healthy runs (misfit) | Element range (x sigma0) | Bad runs (misfit) |
|---|---|---|---|
| 0.003 | 5.5-5.8 % | [0.08, 17] | 28-61 % |
| 0.03 | 6.8-7.1 % | [0.17, 3.2] | 30-60 % |
| 0.1 | 9.2-9.4 % | [0.23, 2.7] | 34-61 % |

Healthy runs are the two 09-29 dry runs; bad runs are E8 lost, wet surface and disc-02. The synthetic 2:1 inclusion is located at 0 degrees at every weight.

- **Weight 0.03.** It removes the electrode spikes for under 1.5 points of misfit. The 15 % misfit gate separates healthy from bad runs at every weight tried, so the gate does not depend on this choice.
- **DAC in the ramp.** Lower current eases polarisation. After the reseat the worst pair sat at 502-515 µA, past the preset's noted 486 µA (the firmware's high-range rating is 1000 µA, so nothing was flagged). Absolute sigma0 is current-normalised, so attempts at different DAC codes are still comparable.
- **Samples capped at 32.** The firmware `n` command clamps to 32 without saying so; 64 would have been recorded wrongly.
- **Contact-fault stop.** No capture setting repairs a contact. Without the stop, a bad nail costs the full ramp: about 4 hours.

## Consequences

- A full ramp is up to about 4 hours. The cheap steps come first (4 and 9 min), the 200 ms step last (77 min).
- Attempts on one disc can differ in DAC, so a later difference image against such a baseline is refused by the settings gate (ADR-0026). This is intended.
- Remaining limits of the absolute model are unchanged from ADR-0041. It is a 2-D circular model with point electrodes and no contact impedance. Even the healthy disc's elements span 0.17-3.2x sigma0, so single-element values are not material properties.
- If disc-02 still sits at about 60 % misfit after the contacts are reseated and dried, its data does not fit a disc model. Treat it as a specimen problem (moisture, cracks, surface film), not a solver problem.

## Verification

`tests/test_absolute.py` covers the ramp values and ceilings, the time estimate against the measured 64 s frame, the contact-fault stop, and synthetic recovery. `tests/test_tree_ert_qt.py` covers the worker's ramp order and the stop. The bench check is unchanged from ADR-0041: disc-01 and disc-08 should peak low near E4-E7 and E10.
