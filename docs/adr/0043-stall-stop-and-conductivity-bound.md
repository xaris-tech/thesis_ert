# ADR-0043: Stop recalibration on a reciprocity stall, and bound element conductivity

- **Status:** Accepted
- **Date:** 2026-10-06
- **Affects:** `tree_ert/absolute.py` (`stop_reason`, `LOG_SIGMA_BOUND`), `tree_ert/qt/worker.py`
- **Related:** ADR-0041, ADR-0042

## Context

Two gaps appeared on disc-08 during the 2026-10-06 session.

1. **The contact-fault stop (ADR-0042) never fired.** It only flags an electrode much worse than the run's median. On disc-08 every electrode read 12-36 %. Median reciprocity across attempts was 19.8, 26.1 and 19.3 %, with no electrode flagged, so the ramp went on into a 23-minute step. disc-05's third attempt (39 %, nothing flagged) showed the same blind spot.
2. **A solver runaway.** Attempt 3 reported a peak of 7×10^17 × sigma0. The Tikhonov prior did not hold elements the data barely constrain.

## Decision

- Recalibration stops when either of these holds:
  - the last 3 refused attempts each flagged a suspect electrode (unchanged), or
  - the last 3 refused attempts each had median reciprocity above 1.2 × the gate (18 %).
- Both the UI worker and `acquire_until_pass` use the same `stop_reason`.
- Element conductivity is clipped to sigma0/100 .. sigma0 × 100 inside the line search.

## Rationale

- **The 18 % stall limit.** It is far enough above the 15 % gate that an attempt which is trending down (19.8 → 9.0 %) keeps going. Every no-improvement sequence seen today stays above it: disc-02 15-21 %, disc-05 30-39 %, disc-08 19-26 %. disc-10, at 13-15 %, was stopped by the contact rule instead.
- **The ×100 bound.** Wood, sap and air voids fit inside it. On the passing disc-01 run the bound changes nothing (range 0.13-3.34×, misfit 7.8 %). The runaway disc-08 attempt now stays inside the bound and is still refused (misfit 58 %).

## Consequences

- A disc whose faces are wet now costs about 30 minutes of ramp (preset + 4 + 9 min), not up to 4 hours.
- A disc stuck between 15 and 18 % still runs the whole ramp. That is accepted: it is close enough that settings might help.
- Elements pinned at the bound mean the solve has no information there. That is reported as-is, not hidden.

## Verification

`tests/test_absolute.py`: `StopReasonTests` (stall, improving run, contact streak, short history) and `ClampTests` (garbage data bounded). Replaying `20261006-163651` and `20261006-150731` gives the numbers above.
