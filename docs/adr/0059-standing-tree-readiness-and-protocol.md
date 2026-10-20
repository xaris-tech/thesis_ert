# ADR-0059: Standing trees are scanned only after a disc rotation test passes, with a fixed electrode and ground-truth protocol

- **Status:** Proposed
- **Date:** 2026-10-08
- **Affects:** methodology; thesis claims about standing coconut palms; `run_record.Conditions` fields operators must fill in
- **Related:** ADR-0041/0057 (absolute imaging), ADR-0058 (validity criteria), ADR-0014 (current-sense miswiring), `a83f52c` (cross-specimen baseline fails)

## Context

No standing tree has been scanned. Every successful image so far is a **difference** image: the same specimen before and after a change. A standing tree has no before scan.

- **Reference trees do not work as a baseline.** Commit `a83f52c` found that cross-specimen comparison cannot separate intact from holed discs: intact scored 0.10-0.85 and holed 0.56-0.74.
- **The absolute image is not yet trustworthy.** Its peaks sit on the worst contacts (ADR-0057). On 2026-10-08, disc-05's absolute peak stayed at 282° before and after drilling.
- **Current does reach the centre.** In the 2026-10-02 saline series a block at the centre was found at radius 0.13. The limit is contact quality and surface wetness, not penetration.
- **Wetness ruins measurements.** A moistened coconut scored 19-47 % reciprocity against 4-5 % dry, and its current fell by a third. A living trunk is wet.
- **The current source is unconfirmed.** If the sense amplifier is tapped before Rs (ADR-0014), current depends on contact resistance, which bark makes worse.

## Decision

A standing tree is scanned only after these steps pass in order:

1. **Instrument.** Resistor ring under 0.2 % reciprocity. A series meter confirms the reported current within a few percent.
2. **Disc detection.** On a good disc: a repeat scan under significance 2, then a drilled hole at significance at least 3 within 30° (ADR-0058).
3. **Absolute rotation test.** On a disc with a known hole, rotate the disc by three electrodes and rescan. The absolute peak must move with the hole, not stay with the electrodes. This decides ADR-0057.
4. **Wet-surface test.** Wet a disc's faces, then repeat with shank-insulated screws. Insulation must recover the dry result.

On the tree:

- **Electrodes:** 12 stainless screws, spaced by tape-measured circumference / 12, at about 1 m height and level. Shanks insulated so only the tip touches wood; same depth every time. E1 faces north, numbered clockwise from above. Bark dried around each screw. No gel unless one contact is open.
- **Record:** specimen ID, circumference, height, electrode protrusion, grounding, weather and time since rain, typed fresh each run.
- **Scan:** a resistor-ring check, then one scan. Re-seat any electrode with markedly low current. Then two back-to-back scans that must meet ADR-0058's criteria 1, 2 and 4. Only then is the absolute image read, and only if step 3 passed.
- **Ground truth:** a known-healthy and a known-damaged palm. Confirm by cutting a disc at electrode height from a palm due to be felled, or by drill-resistance or coring at the image peak. Scan several healthy palms to establish what normal looks like.

## Rationale

- **Rejected: scanning trees now and interpreting later.** Without step 3, an absolute peak cannot be told apart from a contact. Every tree image would be uninterpretable.
- **Rejected: a healthy-tree reference as a baseline.** Ruled out by `a83f52c`.
- **Shank insulation** targets the measured failure mode: current running along a wet surface. It is untested and is why step 4 exists.
- Few, small screws reused in the same holes, because palms do not compartmentalise wounds.

## Consequences

- The tree work waits on at least four bench sessions.
- Every claim about trees needs destructive or semi-destructive ground truth on at least one palm.
- If step 3 fails, absolute imaging cannot image standing trees in its current form. The thesis would then claim only same-tree time-lapse monitoring: a scan now, compared with a scan later.

## Verification

Unverified. Each step above has a pass condition. The record of whether it passed is the run IDs in `scans/index.csv` and a session note.
