# ADR-0057: An absolute PASS does not locate a defect while contacts are uneven

- **Status:** Proposed. Test it with disc-06 E2/E3 re-seat and disc-08 rotation (see `docs/session-2026-10-07-contacts-settle-gel.md`).
- **Date:** 2026-10-08
- **Affects:** thesis claims about absolute imaging; interpretation of `absolute.png`; ADR-0041 gates
- **Related:** ADR-0041/0042/0043 (absolute reconstruction), ADR-0027 (significance), session notes 2026-10-06 and 2026-10-07

## Context

The ADR-0041 gates are reciprocity ≤15 %, misfit ≤15 % and significance ≥2.0. They test that the data are self-consistent and fit a conductivity model. They do not test where the image puts a feature.

Using the mesh electrode angles (E7 = 0°, E4 = 90°, E1 = 180°, E10 = 270°), the peaks on 2026-10-07/08 sat on each disc's worst electrodes:

| Disc | Peak | Nearest electrodes | Worst electrodes / known defect |
|---|---|---|---|
| disc-06 (**PASS ×2**) | 140° | E2/E3 | E2/E3 worst (25-31 %) |
| disc-01 | 316° | E8/E9 | E8-E11 bad (16-24 %); holes near E4-E7 |
| disc-02 | 259° (every run) | E10/E11 | — |
| disc-08 | 12° | E7 | hole near E10 (270°) |

On 2026-10-06, disc-01's unexplained low region was at E10, and that run had just had E10 re-seated. This matches the pattern above.

## Decision

Until a rotation test shows a peak following a known defect, an absolute image that passes the gates is reported as a **self-consistent conductivity estimate**, not as a defect location. Any absolute image cited in the thesis must also state its worst per-electrode reciprocity.

## Rationale

- **Rejected: treat a PASS as localisation.** disc-08 put its peak 90° away from a known hole, and disc-06's peak sits on its worst contacts.
- **Rejected: tighten the gates.** A per-electrode limit might help. But the median gate can pass while two electrodes sit at 30 %, and no gate value has yet been shown to separate contact artefacts from defects.
- **Status is Proposed.** The evidence is circumstantial: four discs, no controlled test. The disc-06 re-seat test would falsify it if the 140° peak stays once E2/E3 are good.

## Consequences

- No absolute-imaging defect claim can be made until the disc-08 rotation test (or an equivalent) succeeds.
- It strengthens the case for a per-electrode reciprocity gate in `tree_ert/absolute.py`. That gate is not implemented.
- Difference imaging on the same disc (the 2026-09-29 drill test) remains the only evidence that a hole can be detected in wood.

## Verification

Unverified. To verify, on dry disc-06 (now 140° on E2/E3):

1. Re-seat E2/E3 into fresh wood.
2. If the peak moves or disappears and E2/E3 fall to about 5 %, accept this ADR.
3. If the peak stays at 140° with good contacts, reject it.
