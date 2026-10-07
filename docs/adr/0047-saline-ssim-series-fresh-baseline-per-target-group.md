# ADR-0047: Saline SSIM series uses a fresh, self-checked baseline per target group, and angle error is the headline metric

- **Status:** Accepted
- **Date:** 2026-10-02
- **Affects:** saline-tank capture methodology, `ssim/` evaluation, thesis localisation claims
- **Related:** ADR-0023, ADR-0025, ADR-0026, ADR-0027, ADR-0046

## Context

The aim was 30 saline-tank runs with wooden blocks at known positions, each
scored by SSIM against a ground-truth mask. On 2026-10-02 the first attempts
failed. Runs 1 and 2 gave the same image at 171°. Wood at E1 (`134418`) gave
0.92× with its peak at 150°. All of them were imaged against one long-lived
session baseline that had not settled: baseline `133531` differed from itself
(frames 1–5 vs 6–10) by 0.188, about the size of a block signal (≈0.21–0.27).
Drift between successive baselines appeared at 150° (E2): 0.221 over 35 minutes
and 0.103 over 40 minutes.

Median reciprocity was 10–13% in every saline run, good ones included. The
2026-09-22 saline runs found wood at the right angle at the same reciprocity.

Once a fresh baseline was captured per group of 2–4 targets, all 12
near-electrode positions were detected (6.5×–35.5×, mean absolute angle error
5.5°). Peaks, however, sat at about 0.35–0.5 R while the blocks were at
about 0.8 R.

## Decision

1. For each group of 2–4 target runs, capture a fresh empty baseline. Always
   capture one immediately before a target near E1, E2 or E3. Accept the
   baseline only if its early-vs-late self-difference peak is well below a
   block signal (achieved: 0.009–0.024).
2. A target imaged against a baseline older than about 40 minutes near the
   drift location (E2) is reported as unconfirmed and repeated.
3. SSIM evaluation reports per run: angle error (the headline), raw SSIM
   against the sharp mask, and SSIM against the mask blurred to the
   point-spread width.
4. Series data lives in `ssim/<series>/` as copies of the runs plus a
   manifest. `scans/` stays the authoritative record.

## Rationale

- **Not a reciprocity gate (≤ 2%).** I proposed that first. It is contradicted
  by the September and October detections at 10–13%. Gating on it would have
  discarded a working setup.
- **Not one session baseline.** The drift sits at E2. Against a stale baseline
  it produces a peak at 150° that the significance ratio cannot tell apart
  from a block at E2.
- **Not raw SSIM alone.** The JAC solver's centre bias and blur put a correctly
  detected block at the wrong radius. Raw SSIM would then grade the
  regularisation, not the instrument, and understate a detection that is
  correct in angle. Reporting raw SSIM beside angle error keeps the radial
  limitation visible rather than hidden.
- **Copy, not move.** Moving runs out of `scans/` would break `index.csv`
  paths and the documented series (ADR-0025).

## Consequences

- More captures: one extra baseline per 2–4 targets.
- The radius result is weak and must be stated as a limitation in the thesis.
  Only angle localisation is claimed for this series.
- Several target fields were filled in after capture from the operator's
  account. Each is marked in `notes`, which bends ADR-0023's "written when the
  run opens" rule. The amendment is visible, not silent.
- Duplicate data on disk (`ssim/` copies). This is small, about 200 KB per run.

## Verification

- `ssim/saline-tank-2026-10-02/manifest.csv` lists, for every run, its
  baseline, the expected angle, the peak angle and the significance.
- Self-difference and drift can be recomputed with
  `tree_ert.reconstruction.reconstruct(frames[:2], frames[-2:], UiSettings(pattern="adjacent"))`
  on any baseline's frames.
- Falsified if a control run (a baseline followed by a second empty capture,
  against a fresh baseline) shows ≥ 2× significance.
- SSIM numbers are not computed yet. The script is pending (see
  `ssim/saline-tank-2026-10-02/NEXT-STEPS.md`).
