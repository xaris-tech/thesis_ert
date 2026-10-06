# ADR-0041: Gate absolute reconstruction on reciprocity, misfit and significance, and re-acquire until it passes

- **Status:** Accepted
- **Date:** 2026-10-06
- **Affects:** `tree_ert/absolute.py`, `absolute_session.py`, `run_record.INDEX_COLUMNS`, thesis claims about absolute imaging
- **Related:** ADR-0002, ADR-0027, ADR-0028, ADR-0032, ADR-0034, ADR-0035, ADR-0039

## Context

The 2026-10-06 session scans ten cut coconut discs: disc-01 with holes near E4-E7, disc-08 near E10, discs 2-7 and 9 with none known, and disc-10 visibly lighter. Most were never scanned before damage, so there is no baseline to difference against (the ADR-0028 problem). `reconstruction.py` refused absolute imaging while reciprocity was open. After the V- wiring fix (ADR-0031) the coconut preset (ADR-0039) measures 4.1-4.7 % median reciprocity and 0.45-0.49 % noise on the dry disc, so the reason for that refusal is gone for this specimen class. A refusal was still needed for runs where it comes back.

## Decision

Each run is solved absolutely on its own. The solve fits a closed-form homogeneous conductance, then runs a damped Gauss-Newton in log-conductance with NaN rows dropped. The image is refused unless three gates all pass:

1. Median reciprocity is at most 15 % (ADR-0032).
2. RMS model misfit is at most 15 %.
3. Significance is at least 2.0. Significance here means the peak of (sigma - sigma0) divided by the peak of a split-half absolute noise image (the ADR-0027 rule).

A refused run is re-acquired with the next `drift_tuning_candidates` profile, cycling `--rounds` times (default 2). Every attempt is recorded as its own run.

## Rationale

- **Misfit gate.** Replaying the recorded 2026-09-29 disc runs: healthy runs fit to 5.7-6.1 %. The E8-contact-lost run (165833) read 31 % and the wet run (151207) 50 %, and both still passed significance (6.3 and 15.5). Significance alone therefore cannot catch a model that does not fit. 15 % sits between the two groups with margin.
- **No DAC escalation.** The coconut preset already runs at the high-range ceiling (620), with the worst pair at 486 of 500 uA. So the ladder varies only settle, samples and warmup.
- **Bounded retries.** Looping without a cap was rejected. A broken contact never passes, and an unbounded loop would hide that behind fresh attempts.
- **Jacobian sign.** pyeit's `compute_jac` returns -dV/dsigma, checked against a finite difference. Using it unsigned made the solve diverge to 10^5 % misfit.

## Consequences

- Absolute values assume a circular 2-D disc with evenly spaced point electrodes. Ovality and contact area are a geometry error the gates do not measure, so sigma0 is comparable between discs mounted the same way, not a calibrated material constant. S/m requires `--thickness-mm`.
- Per-element peaks near electrodes are larger than sigma0 (about 5.8 mS against 2.2 mS on the dry disc). Hole localisation must be checked against the known holes on disc-01 and disc-08 before it is claimed.
- The demo acquisition does not produce physical data and is always refused (93 % misfit). That is expected.
- Three index columns are appended: `absolute_sigma0_ms`, `absolute_misfit_percent`, `absolute_gate`.

## Verification

`tests/test_absolute.py` covers the following on pyeit-forward synthetic data:

- homogeneous recovery
- inclusion localisation and sign
- sign-flip detection
- NaN dropping
- retry-loop termination

Bench check: disc-01 and disc-08 should peak (negative, resistive) within about 30 degrees of E4-E7 and E10. If they do not, the absolute image is not yet locating holes.
