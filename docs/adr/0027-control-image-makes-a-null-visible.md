# ADR-0027: Every difference image is rendered beside the baseline against itself

- **Status:** Accepted
- **Date:** 2026-09-16
- **Affects:** `tree_ert/reconstruction.py`, `tree_ert/qt/`, `run_record.py` index columns, what
  any reconstruction image is allowed to claim, how a null result must be reported in the thesis
- **Related:** extends [ADR-0026](0026-session-baseline-reconstruction-and-a-quantisation-check.md),
  whose "known imperfection" this fixes; [ADR-0004](0004-opt-in-pinned-colorbar.md),
  [ADR-0019](0019-image-the-void-by-inserting-a-target.md), `docs/validity-audit.md` D-05
- **Evidence:** `scans/runs/20260916-175453-coconut-1-2nd-run`,
  `scans/runs/20260916-181821-coconut-1-2nd-run`

## Context

ADR-0026 shipped difference reconstruction and stated a known imperfection plainly: the peak value
is in the solver's arbitrary units while the measurement noise floor is in kohm, so the figure can
state both but cannot compare them. Deciding whether a peak cleared the floor still required
judgement.

That imperfection bit on the first real use, the same day.

Two consecutive captures were taken on the cut coconut trunk with **nothing changed between them**
— same specimen, same settings, no adjustment. The reconstruction rendered a strong, structured,
entirely convincing dipole pattern with `peak -1.461e-01`. The operator asked whether it indicated
a null. It did, and nothing on the figure said so.

Analysing the underlying measurements settled it:

```text
pairs compared              108
within-run noise (median)   0.000323 kohm
baseline->target change     median 0.000619 kohm    max 0.025049
change / within-run noise   median 1.6x             max 4.5x
pairs changing > 3x noise   6 of 108
```

A median change of 1.6x the noise, with the drift spread evenly across all twelve electrodes
rather than localised — every electrode's delivered current rose by 9 to 20 uA, a roughly uniform
7 percent. There was no feature. The image was residual drift stretched to fill an auto-scaled
colour range, and an auto-scaled image of noise is visually indistinguishable from an auto-scaled
image of signal.

This is the exact failure mode the project has fought repeatedly under other names: D-05's
substituted nulls rendering as measurements, ADR-0004's colorbar pinning, ADR-0019's structurally
guaranteed null. Each was fixed locally. None of them made the general case visible.

## Decision

Every difference image is rendered as **two panels sharing one colour scale**: the reconstruction,
and a **control** — the baseline's first half of frames differenced against its second half.

Nothing changed between those halves by construction, so the control is what measurement noise
looks like through this solver, on this specimen, at these settings, in the same arbitrary units
as the image beside it.

`significance()` reports the ratio of the two peaks. Below **2.0** the UI and the figure say
*indistinguishable from noise*. `control_peak` and `significance` join the scans index.

A baseline of fewer than four frames yields no control, and that absence is stated rather than
passed over: the image is then labelled `NO CONTROL IMAGE - significance unknown`.

Applied retrospectively to the two runs above:

```text
target image peak    -1.4613e-01
control image peak   -8.3966e-02
significance          1.74x        ->  indistinguishable from noise
```

The two panels are visually near-identical: the same blue lobe, the same red arc, the same
structure. What the reconstruction was drawing is the instrument's own signature — reproduced
whether or not anything changed — and not the specimen.

## Rationale

**Why the baseline against itself, rather than a computed noise threshold.** The quantity that
matters is the image, and measurement noise reaches the image through the backprojection, the
frame-scaling factor, and the mesh — a transformation with no closed form worth trusting here.
Splitting frames measures the end-to-end result instead of modelling it, using data already
captured, and it automatically carries whatever is wrong with the instrument that day.

**Why a shared colour scale.** Scaling the panels independently would render the noise image
exactly as dramatic as the real one, which recreates the misreading rather than curing it. One
scale is what makes the comparison a glance instead of an arithmetic exercise.

**Why a split-half rather than repeating the baseline capture.** A second capture would take
minutes and would drift relative to the first, so it would measure drift plus noise rather than
noise. The halves are contemporaneous.

**Why four frames minimum.** Two per half is the least that carries any spread. One per half
would make the control a single-frame difference, which understates noise rather than measuring
it — and an understated control inflates significance, which is the dangerous direction.

**Why 2.0 as the threshold.** A judgement call, deliberately modest. It is a floor below which a
claim is certainly unsupportable, not a bar above which one is established. The observed null
scored 1.74, which is close enough to the line to show the threshold is not generous. Nothing
here says 3.0x is a detection; it says 1.74x is not.

**Alternatives rejected.** Significance masking — greying out sub-threshold elements — was
considered and deferred: it needs a per-element threshold rather than a peak ratio, and it hides
data rather than contextualising it, which is the wrong default for a research instrument. Noise
weighting of pairs by measured SNR is the natural next step and is deliberately not bundled here,
because it changes what every image means and deserves its own decision.

**Known imperfections.** The peak ratio compares two maxima and ignores spatial agreement
entirely: an image could coincidentally match its control's magnitude while differing completely
in shape, or vice versa. The operator is expected to look at both panels, not only the number.
The control also measures noise *within* the baseline capture, which is shorter than the interval
between baseline and target — so slow drift over that longer gap is not represented, and
significance is therefore optimistic.

## Consequences

**Easier.** A null is visible rather than inferred. The two-panel figure is self-contained
evidence for a thesis appendix: it shows the result and the instrument's own noise in one frame,
on one scale. `significance` in the index makes a whole series sortable by whether anything was
detected at all.

**Harder.** Reconstruction now runs twice per capture, roughly doubling that step. Figures are
wider and are two-panel, which is a change for anything that consumed the old single-panel image.
Baselines shorter than four frames lose the check entirely.

**Committed to.** No difference image from this instrument should be presented without its
control. A single-panel reconstruction in the thesis is now an incomplete result, not merely a
plainer one.

**Will bite later.** A significance above 2.0 is not a detection and the number invites being read
as one. The threshold has no statistical meaning — it is not a p-value, and calling something
"3x noise" states a ratio of two peak magnitudes and nothing more. Second, the control shares the
baseline's frames with the reconstruction itself, so the two are not independent; a baseline with
one anomalous frame corrupts both panels in the same direction, which makes them agree for the
wrong reason.

## Verification

- `tests/test_reconstruction_module.py` — `ControlImageTests`: fewer than four frames yields None
  rather than a fabricated control; identical frames give a zero-noise image; drifting frames give
  a non-zero one. `SignificanceTests`: an image the size of its noise scores 1.0; zero noise with
  a real image is infinite rather than a crash. `SaveTests`: the control panel is drawn, and
  `control_values` and `significance` reach the npz.
- `tests/test_tree_ert_qt.py` — the control reaches the window through the `reconstructed` signal;
  an absent control is labelled rather than passed over.
- Full suite: 390 tests passing.
- **Reproduced on real data**: the 2026-09-16 unchanged-specimen pair scores 1.74x and renders two
  near-identical panels. Re-runnable from `scans/runs/` at any time.

To falsify: capture a baseline, insert a metal rod, capture a target, and confirm the panels differ
visibly and the significance rises well above 2. If a known, large, correctly-placed target does
not separate from its control, the instrument cannot image at all and the problem is upstream of
this ADR.
