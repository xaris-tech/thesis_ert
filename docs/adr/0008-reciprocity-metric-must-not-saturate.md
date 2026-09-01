# ADR-0008: Score reciprocity with a non-saturating metric and report sign flips separately

- **Status:** Accepted
- **Date:** 2026-09-01
- **Affects:** `phase3a_unified_reconstruct.py` (`reciprocity_errors`, `filter_by_reciprocity`,
  `--reciprocity-threshold-pct`, reciprocity CSV), any threshold calibrated from it
- **Related:** [ADR-0003](0003-reciprocity-as-report-not-gate.md),
  [ADR-0009](0009-fix-e5-contact-before-further-capture.md), `docs/validity-audit.md` L-02

## Context

The first live reciprocity run (2026-09-01, adjacent, DAC 100) reported 47 of 54 scored pairs
above the 10% threshold, worst 200.00%. Read at face value that condemns most of the rig.

It does not. The metric is

```python
denom = max((abs(value) + abs(other)) / 2.0, 1e-9)
errors[key] = abs(value - other) / denom * 100.0
```

For any two values of opposite sign, `abs(value - other) == abs(value) + abs(other)`, which is
exactly twice the denominator. The result is **exactly 200%, for every sign-crossing pair,
regardless of magnitude**. Measured, from that run:

```
I=(6,7) V=(4,5):  -0.33242  recip +0.02263   err 200.00%   <- 15x magnitude gap
I=(2,3) V=(7,8):  +0.00376  recip -0.00376   err 200.00%   <- magnitudes identical
```

A gross disagreement and a perfect magnitude match score the same. `worst=200.00%` is not a
worst case, and sorting by this column cannot surface the worst pair — the headline number the
runbook tells the operator to act on is uninformative in precisely the regime it fires.

The saturation also hid the real signal. Where the metric does not saturate it shows this rig
is reciprocal to ~0.6% on strong pairs, with a genuine 111% failure on `I=(4,5) V=(8,9)`
(`+0.01393` vs `+0.04910`) that ranked below dozens of saturated 200% rows.

Why so many sign crossings: distant-pair transfer resistances were 0.003-0.006 kOhm against a
control-drift floor of ~0.010 kOhm measured the same session. Those measurements are below the
noise floor, so their sign is arbitrary. That is offset domination, which `AGENTS.md` already
predicts for distant pairs — not a wiring fault.

## Decision

Replace the mean-magnitude denominator with one that cannot saturate, and stop encoding a sign
disagreement as a percentage. Score magnitude agreement against `max(abs(a), abs(b))`, and
report a sign flip as a separate flag on the row.

## Rationale

A relative error whose denominator shrinks as the numerator grows is unbounded-in-principle and
constant-in-practice; it cannot rank. `max(abs(a), abs(b))` is bounded, monotonic in the actual
disagreement, and reduces to the familiar relative error when signs agree.

Sign deserves its own column because it means something different from magnitude error. On
this instrument a flipped sign at low amplitude is the expected consequence of offset
domination, while a flipped sign at high amplitude would be a wiring fault. Folding both into
one number destroys that distinction — which is exactly what happened here.

Alternatives rejected:

- **Compare magnitudes only (`abs(abs(a) - abs(b))`).** Removes the saturation but discards
  sign entirely, so a genuinely reversed high-amplitude measurement — a real fault mode — stops
  being detectable.
- **Leave the metric and raise the threshold above 200%.** Disables the check.
- **Exclude sub-noise-floor pairs before scoring.** Worth doing, but it is a separate decision
  about what is measurable, and it would mask the defect rather than fix the metric. The metric
  must be correct on whatever it is handed.

## Consequences

Easier: the reciprocity CSV becomes sortable, so "which electrodes recur in the worst rows"
— the diagnostic the runbook's rung 7 is built on — starts working. Thresholds become
calibratable, unblocking the ADR-0003 plan to set a real one from collected distributions.

Harder: scores from before this change are not comparable with scores after it, and any
threshold discussed in prior notes refers to the old metric.

This does not change ADR-0003: reciprocity stays a report, not a gate. `filter_by_reciprocity`
remains defined, tested, and uncalled. That decision is what prevented the saturated metric
from discarding ~87% of a healthy dataset, and this ADR is the argument for keeping it that way
until the metric has been calibrated on real distributions.

## Verification

`tests/test_phase3a_unified_reconstruct.py::TestReciprocityCheck` covers the metric:
`test_score_is_monotonic_across_a_sign_boundary` asserts that `(+1,-1)`, `(+1,-10)` and
`(+1,-100)` produce three increasing scores, where the previous metric returned 200% for all
three. `test_sign_flip_is_reported_separately_from_magnitude` pins that a perfect magnitude
match with a flipped sign scores 0% error and sets the flag.

Re-scored against the 2026-09-01 capture
(`phase3a_logs/phase3a-v2-adjacent-20260901-171117.csv`), the metric now returns **54 distinct
scores for 54 pairs** spanning 0.70% to 99.84%, against 47 identical 200.00% values before.
The worst-third electrode frequency became E5 x11, E4 x9, E3 x7 — E5 now ranks first,
independently agreeing with the drive-current evidence in
[ADR-0009](0009-fix-e5-contact-before-further-capture.md). Under the old metric E5 tied at 9
in a flat distribution that named no suspect.

Falsified if any two pairs with different magnitude ratios ever score identically, or if a
re-run reports a median of exactly 200.00%.

The 10% threshold remains the ADR-0003 placeholder. It is now calibratable — the distribution
is no longer saturated — but has not been calibrated, and 42 of 54 pairs sit above it. Setting
a real value needs several runs on repaired hardware, so it stays a report and not a gate.
