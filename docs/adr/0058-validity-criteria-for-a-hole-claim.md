# ADR-0058: Validity criteria for a hole claim: reciprocity, noise, repeat scan, significance margin

- **Status:** Proposed
- **Date:** 2026-10-08
- **Affects:** methodology; thesis claims about defect detection; `tree_ert/absolute.py` (`NOISE_LIMIT_PERCENT`, used by ADR-0060)
- **Related:** ADR-0027 (significance 2.0), ADR-0032 (reciprocity 15 %), ADR-0041 (absolute gates), ADR-0057 (peaks on contacts), ADR-0060

## Context

The code gates an image on median reciprocity ≤ 15 %, model misfit ≤ 15 % (absolute only) and significance ≥ 2.0. There is no noise gate, and nothing requires a repeat scan. On 2026-10-08 these gates let through, or nearly let through, results that were not about the specimen:

- **disc-06 against itself, untouched** (`20261008-003801` against `-002746`): significance 2.2.
- **disc-05, two untouched scans** (`20261008-124142` against `-122526`): a broad two-sided difference pattern at 10.6× the noise image. The baseline's noise was 2.2 %, the repeat's 7.9 %. The noise image comes from the baseline alone, so it under-states the noise and inflates the ratio.
- **disc-05 holed** (`140202` to `144835`): the absolute peak stayed at 282°, exactly where it was on the intact disc.

Reference across the documented series (`scans/index.csv`):

| Series | Median reciprocity | Noise | Outcome |
|---|---|---|---|
| Resistor ring | 0.07-0.09 % | 0.13 % | electronics |
| Saline tank, 2026-10-02 | 10.4-15.8 % | 0.9-1.5 % | 18/18 blocks located within 1-18° |
| coconut-tree-1 (2026-09-23), dry coconut (2026-09-29) | 2.5-4.9 % | 0.4-0.9 % | best real specimens |
| Same coconut, moistened (2026-09-29) | 19-47 % | 3-22 % | unusable |
| disc-01, disc-06 (dry) | 6.5-8.7 % | — | only discs near the gates |
| disc-05 (2026-10-08) | 20-24 % | 2-8 % | fails |

Every run that imaged well had noise near 1 %. Every failed one was well above 3 %.

## Decision

A difference image supports a hole claim only if all of these hold:

1. median reciprocity ≤ 15 % in **both** runs (unchanged gate);
2. median noise (frame-to-frame pair spread) ≤ 3 % in **both** runs;
3. per-electrode current within about 5 % between the runs, so contacts did not change;
4. a repeat scan of the intact specimen, with nothing changed, scores significance **< 2**;
5. the hole image scores significance **≥ 3**.

An absolute image additionally needs ADR-0057 resolved (the peak must follow a rotated hole) before it supports any location claim.

## Rationale

- **Rejected: tightening reciprocity to 10 %.** The saline tank located every block at 10.4-15.8 %. A 10 % gate would refuse the only series that is known to work.
- **Rejected: a worst-electrode limit (about 30 %).** Good tank runs still had one electrode at 89-99 %. The worst electrode does not separate good runs from bad ones.
- **Noise ≤ 3 %** is the threshold that best separates good runs from bad in the table above. It also catches the disc-05 case, where the noise image came from a quieter baseline than the target.
- **Repeat scan.** Significance compares against the noise inside one run. It cannot see drift *between* runs, which is what the disc-05 pattern was. Only an untouched repeat measures that drift.
- **Significance 3, not 2.0.** An untouched disc already reached 2.2. The 3.0 is a judgement call: it sits above every untouched pair seen so far and below the drill test's 3.6 (`b059058`). It may need revisiting once more repeat pairs exist.

## Consequences

- Most existing disc runs fail criterion 2 or 4, or were never tested for it. No current disc result supports a hole claim under this ADR.
- Every specimen now costs at least one extra scan, the untouched repeat, at about 10 minutes.
- Criteria 2-5 are not enforced in code. The UI still shows an image that passes only the 15 % and 2.0 gates. Only the 3 % noise limit is used in code, as a recalibration input (ADR-0060).
- 3.0 rests on few repeat pairs (disc-06 at 2.2, disc-05 well above it).

## Verification

Unverified as a gate. To verify: collect at least five untouched repeat pairs on good discs and check that all score below 2. Then drill a known hole and check that it scores at least 3 with the peak within 30° of the hole.
