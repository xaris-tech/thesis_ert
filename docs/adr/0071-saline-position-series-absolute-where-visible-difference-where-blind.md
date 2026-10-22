# ADR-0071: Saline position series judged by absolute where visible, by difference where blind

- **Status:** Accepted
- **Date:** 2026-10-22
- **Affects:** `position_series.py`, the handoff 2026-10-19 §3.5 saline series, thesis localisation claims for saline
- **Related:** ADR-0041 (absolute gates), ADR-0047 (saline SSIM series), ADR-0064, ADR-0067 (E1/E2 excluded, E1–E3 blind), ADR-0068 (±30° and significance ≥2.0), ADR-0070 (unexcluded first)

## Context

The §3.5 series (empty tank first and last, wood at E1–E12, the six opposite pairs, the centre;
3 runs each at DAC 400, settle 10 ms, 16 samples) was deferred until the E1/E2 channel fault was
fixed. The fault is not fixed: on 2026-10-20 the empty tank with all electrodes was refused at
60–61 % misfit (3/3), and 9–11 % with E1/E2 excluded. Excluding E1/E2 blinds the absolute image in
the E1–E3 sector (120–180°), so a block at E1, E2 or E3, or the pairs 1+7, 2+8 and 3+9, cannot be
judged absolutely.

A difference image against an empty-tank baseline taken in the same session, with nothing
remounted, does not need the exclusion: a fault that is the same before and after cancels, which
is why ADR-0068 asks for a difference image on discs as well.

The operator decided on 2026-10-22 to run the series now: absolute for the positions that are not
blind, difference for the positions that are.

## Decision

`position_series.py` records every run and always produces three results: the unexcluded absolute
solve with a leave-one-out sweep (ADR-0070), the absolute solve with the standing exclusion
(default E1/E2), and a difference image against the last run of the opening empty tank, using all
electrodes, with a split-half control for significance. The **headline** for a position is the
difference image if any of its blocks sits at an electrode in `--blind` (default E1–E3), and the
excluded absolute image otherwise. A block is *located* when the headline image puts its trough
(absolute: gated pass, trough lobe centroid; difference: significance ≥2.0, most negative element, since wood is resistive) within ±30° of
the nearest block.

## Rationale

- **Waiting for the E1/E2 fix** (the handoff's plan) was rejected by the operator: the fix needs
  8 wire moves and a firmware channel-map change, and the series can show now whether the
  instrument localises in the 300° it can see.
- **Absolute everywhere, accepting E1–E3 as missing**, would leave a quarter of the ring with no
  result at all.
- **Difference everywhere** would drop the absolute claim, which the thesis needs (ADR-0068).
- The blind set is a flag, not derived from the exclusion: the 2026-10-20 handoff names E1–E3
  blind under the E1/E2 exclusion, but E12 (the other neighbour of E1) is not, so no simple rule
  from the excluded set reproduces it.
- Both images are always computed because it costs seconds and no bench time, and it shows
  whether the two agree where both are available.
- ±30° and significance 2.0 are reused from ADR-0068 and ADR-0027 rather than chosen anew.

## Consequences

- The series has two kinds of localisation result. A thesis claim must say which positions rest
  on difference imaging only; difference images are not absolute ones and cannot say anything
  about the bulk conductivity in that sector.
- The difference reference is a single empty-tank run. Drift over the ~4.4 h series adds to every
  difference image; the closing empty tank, differenced against the opening one, measures it.
- For pairs, "located" uses the nearest block only; a pair image that finds one block of two still
  counts. The angle error is reported per run so a stricter reading is possible later.
- Warm-up frames are captured only before the first repeat of a position; repeats follow at unchanged settings with the tank untouched, so they need none. Saves about 2 min a repeat.
- When E1/E2 are fixed, rerun with `--exclude ""` and `--blind ""`; this ADR then no longer applies.

## Verification

`tests/test_position_series.py` covers the series list, the headline rule, angle error from the
mesh's electrode positions, and the located rule. `--demo` runs the whole path without hardware.
Nothing here is verified on the bench yet; the first real series is the check, starting with the
closing empty tank against the opening one, which must not show a located block.
