# ADR-0064: Exclude a known-faulty board channel from the absolute solve

- **Status:** Accepted
- **Date:** 2026-10-14
- **Affects:** `tree_ert/settings.py` (`absolute_exclude_electrodes`), `tree_ert/absolute.py`
  (`exclude_electrodes`, `evaluate`, `contact_fault`, `excluded_text`), `tree_ert/qt/` (settings
  panel field *Absolute: exclude*), every absolute image of the saline tank, thesis claims about
  absolute conductivity
- **Related:** ADR-0002 (drop, do not substitute), ADR-0014/0017 (current-source repair),
  ADR-0032 (suspect electrodes), ADR-0041/0043 (absolute gates, contact-fault stop),
  ADR-0013 (Howland ratio match)

## Context

Every saline-tank absolute solve has been refused on model misfit: 55.9-60.1 % on 2026-10-14,
63.8-66.9 % on the 2026-10-02 SSIM series, against a 15 % gate. The resistor ring at the same
settings passes (11.9 %). The contact check flags E1 and E2 on every saline series (10-02: E2
87 %, E1 46 %; 10-14: E2 82-90 %, E1 65-75 %) and never on the ring.

Three causes were candidates, and the evidence of 2026-10-14 separates them:

1. **Current source.** A dummy-load sweep (`exports/dummy-load-20261014.csv`, ring 202 ohm vs ring
   + 1 kohm) fits Rout ~770 ohm at every DAC code, flatness ~69 %, with 154 mV of output at DAC 0.
   Pin-5 wiring re-measured correct (pin5-I_SRC_OUT 0, pin5-pin1 10, pin5-pin2 110 ohm). The
   resistor readings R1 4.984k, R2 98, R3 5.015k, R4 100.0 give a 1.4 % ratio mismatch, which
   predicts Rout = Rs / e ~720 ohm. So the source is load-dependent, but the ring passes absolute
   with this same source because every reading is normalised by its measured current. The
   source is not what breaks the saline fit.
2. **Model.** Point electrodes in a circle, no contact impedance.
3. **Channels E1/E2.** Swapping nails E1<->E12 and E2<->E3 (runs 20261014-120323 to -121537) left
   the flags on channels E1/E2: the fault follows the board, not the nail.

Re-solving the recorded frames offline with E1/E2 measurements removed:

| Run | all 108 | without E1,E2 (56) | without E1-E3 (42) | control: without E5,E6 |
|---|---|---|---|---|
| ring 20261014-104435 | 11.9 % | 10.9 % | 10.1 % | 11.0 % |
| saline 20261014-105518 | 59.5 % | 11.3 % | 6.0 % | 57.5 % |
| saline 20261014-110234 | 59.0 % | 10.9 % | 6.4 % | 59.5 % |
| saline 20261014-112141 | 55.9 % | 9.6 % | 6.1 % | 58.0 % |
| saline 20261002-135739 | 63.8 % | 13.2 % | 5.5 % | 64.3 % |
| saline 20261002-170541 | 66.9 % | 13.4 % | 6.7 % | 67.7 % |

Removing a healthy pair (E5/E6) changes nothing, so the gain is not from fitting fewer rows. The
model fits saline to ~6 % once E1-E3 are out. The misfit is the E1/E2 channels.

## Decision

Add `UiSettings.absolute_exclude_electrodes` (1-based, at most 6). The absolute solve drops every
record that drives or senses on a listed electrode before averaging, so those pairs become NaN rows
the solver already skips (ADR-0002). The reciprocity gate and the contact-fault stop rule are
computed on the same filtered frames. The figure caption and the log line say
`EXCLUDED E1 E2: 56/108 pairs`. Capture, the run record's frames and difference imaging are
unchanged.

## Rationale

- **Fix the board instead.** The right fix, and still wanted: clean flux around the E1/E2 mux
  pins and header, or move the wires to spare mux channels 12-15. Not possible at the time;
  this setting lets the session proceed and is removed by setting it empty once the board is fixed.
- **Down-weight instead of drop.** A weight is a judgement-call constant with no measured basis;
  dropping matches ADR-0002 and is what the evidence above actually tested.
- **Exclude automatically from the contact check.** Rejected. The flag is a diagnostic with a
  threshold of its own (ADR-0032); letting it silently remove data would hide exactly the fault an
  operator needs to see. Exclusion is an explicit, recorded operator choice.
- **Also exclude from difference imaging.** Not done. Baseline and target share the E1/E2 error
  and it cancels; 10-02 localised blocks to within 1-11 deg with all pairs.

## Consequences

- On the adjacent pattern, excluding two neighbouring electrodes removes 52 of 108 pairs. The
  image has little sensitivity near the excluded electrodes (E1-E3 sit at 120-180 deg in image
  angles) and any structure there should not be claimed.
- σ0 shifts slightly with the subset (2.93 to 2.87 mS on 105518); compare σ0 only between runs
  with the same exclusion.
- The setting is saved with the UI settings and recorded in every run's `conditions.json`. An
  image made with it is not comparable to one made without it, and the caption says so.
- The current source remains load-dependent (Rout ~770 ohm, 154 mV offset at DAC 0). Absolute
  values rely on per-reading current normalisation, not on a known injected current. ADR-0013's
  ratio-match work (a ~360 kohm resistor across R1, confirmed by a re-sweep) remains open.

## Verification

- `tests/test_absolute.py::ExcludeElectrodesTests` and
  `tests/test_tree_ert_settings.py::AbsoluteExcludeElectrodesTests`.
- The table above is reproducible from the recorded `frames.csv` of each run.
- Falsified if a cleaned board still needs exclusion on a fresh saline baseline, or if a target
  placed near E1-E3 is imaged at a confident peak while E1/E2 are excluded.
