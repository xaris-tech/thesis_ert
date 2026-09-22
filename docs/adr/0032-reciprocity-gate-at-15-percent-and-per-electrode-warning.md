# ADR-0032: Reciprocity gate at 15 %, with a per-electrode contact warning

- **Status:** Accepted
- **Date:** 2026-09-22
- **Affects:** `tree_ert/reconstruction.py` (`RECIPROCITY_GATE_PERCENT`), `tree_ert/capture_view.py` (`electrode_reciprocity`, `suspect_electrodes`, `SessionSummary.suspect_electrodes`, session readout and `summary.txt`)
- **Related:** supersedes the threshold of ADR-0030 (the rest of ADR-0030 stands); ADR-0031

## Context

ADR-0030 set the gate at 10 % median reciprocity error, chosen from literature before any working
measurement existed, and noted it would need revisiting with measured evidence. After the V- wiring
fix (ADR-0031) that evidence exists, all from 2026-09-22:

| Run | Condition | Median | Image (offline, gate bypassed) |
|---|---|---|---|
| `143652-resistor-circle` | resistor ring | 0.1 % | n/a, instrument's own floor |
| `145115`, `151800` (baselines) | saline, empty | 12.1 %, 11.2 % | — |
| `150439`, `145825` | wood at E8/E9 | 9.9 %, 11.5 % | peak 316°, 14.3× / 12.5× noise |
| `153116`, `152422` | wood at E4/E5 | 9.1 %, 8.8 % | peak 69°, 11.0× / 10.7× noise |
| pre-fix, all specimens | broken wiring | 57–95 % | useless |

The 10 % gate refused every one of these images because a baseline sat at 11–12 %, although
the images localised the wood correctly, repeatably, and followed it when it moved.

Per electrode, the healthy nails read 8–11 %. The median was raised by one bad contact: E2 at
70 %, with its neighbours E1 (47 %) and E3 (44 %) lifted by sharing pairs with it. The median
could not show this; it took a manual analysis to find.

## Decision

- The gate becomes **15 %** median reciprocity error, on both runs, with the rest of ADR-0030
  unchanged (image refused, capture kept, stamped override).
- The session readout and `summary.txt` name any electrode whose pairs' median error exceeds
  **both 2× the run median and 15 %**, worst first, as
  `Check electrode contact: E2 70%, E1 47%, E3 44% (all pairs median 11%)`.
  This is a warning; it never blocks.

## Rationale

- **15 %, not 10 %:** 10 % sits on the measured floor of healthy nail electrodes in saline under DC,
  so the gate flipped on noise and refused valid images. 15 % passes every measured working run
  with margin and still rejects the broken instrument (57 %+) by a factor of four.
- **Not 20–30 %:** nothing yet shows images stay correct there, and a trunk will be worse than
  saline (wood-metal contact). A loose gate on a tree, where there is no known target, would admit
  broken electrodes silently. Loosen further only on evidence (trunk runs that still pass the
  move and remove tests).
- **Per-electrode warning, not a per-electrode gate:** today's images were correct with one bad
  electrode, so blocking on it would refuse good results. What was missing was knowing *which*
  nail to fix. Factor 2 and floor 15 % are judgement calls: they flag E1–E3 on the measured
  baseline and nothing on the resistor ring (0.1 % overall).
- The operator chose 15 % after seeing these numbers.

## Consequences

- Today's saline runs would pass the gate; images will be produced without override.
- A single bad contact can now degrade an image without refusing it. The warning line is the
  guard; it relies on the operator reading it. The red patch near E2/E3 in today's images is
  likely that contact, not a feature of the tank.
- The warning appears in the UI session box and `summary.txt`, but **not** in `index.csv`.
- Neighbours of a bad electrode are flagged with it; the worst-first order points at the cause.
- The CLI and Tkinter UI are still ungated (ADR-0030).

## Verification

- `tests/test_reconstruction_module.py::ReciprocityGateTests`: threshold 15, a measured 11.2 %
  run passes, 15.0 passes, 15.1 fails.
- `tests/test_capture_view.py::SuspectElectrodeTests`: measured E1–E3 case flagged in order,
  uniform run and resistor-ring case not flagged, per-electrode median, one-based readout.
- Checked against recorded data: `151800` gate PASS with `E2 70%, E1 47%, E3 44%` named;
  `153116` PASS with `E2 71%, E1 56%, E3 44%`; `143652` ring PASS, no warning.
- **Not verified:** images produced through the UI at the new threshold, and any trunk run.
