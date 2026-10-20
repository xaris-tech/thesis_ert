# ADR-0060: Recalibration chooses each attempt from the earlier results, with settle limited to 10-50 ms

- **Status:** Accepted
- **Date:** 2026-10-08
- **Affects:** `tree_ert/absolute.py` (`next_settings`, `acquire_until_pass`; `recalibration_ladder` removed), `tree_ert/qt/worker.py` (`CaptureRequest.recalibrate_max_attempts` replaces `recalibrate_rounds`), `absolute_session.py` (`--max-attempts` replaces `--rounds`), the Recalibrate tooltip
- **Related:** supersedes the ramp in ADR-0042 (its solver regularisation and contact-fault stop stand); ADR-0043 (stop rules, unchanged); ADR-0058 (3 % noise limit)

## Context

ADR-0042's recalibration walked a fixed ramp whatever the previous attempt measured: settle 10 / 30 / 50 / 75 / 100 / 150 / 200 ms, with samples, warmup, frames and DAC varied alongside. Two bench findings since then work against it:

- **Longer settle makes wood worse.** On disc-01 with unchanged contacts (per-electrode current within 2 %), reciprocity was 13.9 % at 100 ms, 6.5 % at 30 ms and 7.3 % at 10 ms. The likely cause is polarisation during the dwell. Four of the ramp's seven steps sit above 50 ms, and the late steps cost 15-23 minutes each.
- **Different failures need different responses.** On disc-05 (2026-10-08), `122526` failed with quiet data (noise 2.2 %) and `124142` failed with noisy data (7.9 %). A fixed ramp treats both the same.

## Decision

`next_settings(start, tried)` picks each attempt from the finished ones:

1. The first attempt is the operator's settings.
2. From the attempt with the lowest median reciprocity so far: if its noise exceeds 3 %, average more at the same settle (samples 32, frames +4 up to 16, warmup +5).
3. Otherwise try the nearest untried settle in 10 / 20 / 30 / 40 / 50 ms.
4. Then one attempt at 90 % DAC.
5. Stop at 6 attempts, when nothing untried is left, or when a stop rule from ADR-0042/0043 fires.

Pattern, current range and electrode mapping never change.

## Rationale

- **Rejected: keeping the ramp and only capping settle.** That still ignores whether the failure was noise or reciprocity, and still spends attempts on changes the data already ruled out.
- **Rejected: a numerical optimiser over all parameters.** Six attempts at about 10 minutes each is too few samples for one, and its choices would be hard to explain on a session log.
- **Climbing from the best attempt, not the latest** means one bad attempt does not drag the search away from settings that worked.
- **10-50 ms** brackets the measured optimum (30 ms) one step either side, plus 50 ms. 50 ms is the last step of the old ramp before reciprocity was seen to worsen.
- **The honest limit.** On the discs, settings moved reciprocity by a few percent, while contacts and wetness moved it by 10-30 %. The main gain is shorter, more relevant attempts. The ADR-0043 stop rules still send the operator to the physical fix.

## Consequences

- Recalibration never runs above 50 ms settle. A medium that needs long settle, such as a high-resistance or very dry specimen, would not get it. The operator can still set any settle by hand for the first attempt.
- `recalibrate_rounds` and `--rounds` are gone. Re-running Recalibrate starts a fresh search.
- Attempts can repeat a settle value with different averaging, so the time estimate is per attempt, logged as before.
- Settle values 20 and 40 ms are new to the firmware's use. Both are within the range it accepts, but neither has been run on the bench yet.

## Verification

`tests/test_absolute.py::NextSettingsTests` covers the first attempt, the noisy and quiet responses, climbing from the best attempt, the 10-50 ms limit, no repeats, the cap and the firmware ceilings. `tests/test_tree_ert_qt.py::test_recalibration_adapts_until_attempts_exhausted` drives the worker end to end.

Replayed on recorded inputs (2026-10-08):

| Input | Next attempt |
|---|---|
| disc-05 `122526` (21.7 %, noise 2.2 %) | settle 20 ms |
| disc-05 `124142` (23.2 %, noise 7.9 %) | settle 30 ms, frames 14 |

Not yet verified on the bench.
