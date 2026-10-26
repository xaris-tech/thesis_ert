# Weekly Status Report — 2026-W38 (14–20 September 2026)

**Project:** Low-cost 12-electrode DC ERT prototype for coconut trees

## 1. Summary

The capture workflow was rebuilt. Every scan is now a self-contained record with its
physical conditions, and a new PyQt6 capture UI replaced the Tkinter UI for new work. A
saline tank was adopted as the reference phantom, and the first saline and trunk captures
were taken (58 runs on 16–17 September).

## 2. Circuit construction

Electrode insertion depth decided and documented (ADR-0020).

## 3. Testing and verification

- **Reciprocity gate** in the Qt UI: images are refused when reciprocity is too high
  (ADR-0029, ADR-0030).
- Settings are checked before differencing: two runs are only compared if pattern, current
  range, DAC, settle, samples and electrode mapping match (ADR-0026).
- Quantisation check: reports how many ADC steps separate each forward/reverse pair
  (ADR-0026).

## 4. Scans

- **Per-run records** (ADR-0023, ADR-0025): `scans/runs/<timestamp>-<label>/` with
  `conditions.json`, unaveraged `frames.csv`, raw serial text and photos; one row per scan
  in `scans/index.csv`; an append-only `session.log`.
- **PyQt6 capture UI** (`tree_ert_qt.py`, ADR-0024). The Tkinter UI is frozen.
- 58 runs: saline tank and trunk captures, reciprocity checks and baselines. One run
  (`20260916-161618-coconut`) is synthetic demo output and is not hardware data.

## 5. Difference imaging

- **Session baseline:** the first run of a session is the baseline; later runs are
  differenced against it (ADR-0026).
- **Control image** shown beside every image, from the baseline's own frames split in two.
  Significance under 2.0 means the result cannot be told from noise (ADR-0027).

## 6. Absolute imaging

Still blocked by reciprocity.

## 7. Saline tank

- **Adopted as the phantom** (ADR-0021) to separate specimen-side faults from
  instrument-side faults; saline concentration to be titrated with the instrument itself
  (ADR-0022).
- First tank captures taken. Reciprocity in the tank was 73–95 %.

## 8. Resistor ring

No change.

## 9. Wood discs

No change. ADR-0028 records that a diseased tree has no healthy baseline of its own to
difference against.

## 10. 3D-printed case

No change. Case designed and printed in W28–W34; fit checked after the board rework in W37.

## 11. Risks and blockers

| Risk | Note |
|---|---|
| Reciprocity error 73–95 % in saline | Cause still unknown; images not yet trustworthy |

## 12. Plan for next week

Build the resistor ring to test whether the reciprocity fault is in the instrument or the
electrodes.
