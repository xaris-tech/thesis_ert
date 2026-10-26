# ADR-0068: A disc hole counts as detected only if difference, absolute and sham all agree

- **Status:** Accepted
- **Date:** 2026-10-21
- **Affects:** thesis claim "the instrument detects a drilled defect in a coconut disc"; bench protocol in `docs/handoff-2026-10-20/README.md` §3
- **Related:** ADR-0027 (significance), ADR-0041 (absolute gates), ADR-0046 (cross-specimen baseline), ADR-0066 (leak floor), ADR-0067 (E1/E2 excluded, E1–E3 blind)

## Context

disc-06 is the first specimen to be drilled. Before drilling (2026-10-20) it is very repeatable
(σ0 5.78–5.95 mS over 7 runs, noise 0.37 %, current 461–468 µA at DAC 400) but every absolute
solve is refused on misfit (36–40 % at DAC 400, 18–21 % at DAC 620) because of the E4 screw
contact; without E4 the misfit is 2.1–2.5 %. The disc also lost about 2.5 % of σ0 over that
session, a uniform drift that appears in any difference image.

Each image type alone can fake a detection:

- A **difference** image cancels contact faults, but drift or handling between the before and
  after runs also produces a trough, and nothing in the image tells the two apart.
- An **absolute** image does not depend on drift between runs, but a bad contact puts a trough
  beside its electrode (disc-06 has a fixed trough at ~75°, beside E4), which looks like a defect.

The criterion has to be fixed before drilling, so the result cannot shape it.

## Decision

A hole is reported as detected only when all three hold, with E1/E2 excluded (ADR-0067),
adjacent pattern, DAC 400, settle 10 ms, 16 samples, 5 warm-up + 10 frames:

1. **Difference.** Each after-run D1–D3, differenced against the last baseline B3 of the same
   unremounted disc, shows a resistive trough whose centroid is within **±30°** of the drilled
   angle, with significance **≥2.0** (ADR-0027); the three centroids agree within about 15°.
2. **Absolute.** Baselines B1–B3 pass the ADR-0041 gates (misfit ≤15 %, reciprocity ≤15 %,
   significance ≥2.0) with no trough in the drill sector; D1–D3 pass the same gates with the
   trough within ±30° of the drilled angle. B1–B3 must agree within 2 % on σ0 and on current.
3. **Sham.** A run S1, taken after waiting as long as drilling takes and handling the disc as
   drilling will (without drilling), differenced against B3, is empty: significance <2.0 and no
   trough in the drill sector.

The hole goes in the usable sector (E4–E9, about 300° through 90°), through the full thickness,
about 20 % of the disc diameter. Failing any criterion is reported as a failure, with which one
failed. Excluding E4 as well (30/108 pairs, 60–180° blind) is allowed only as a declared fallback
and is reported as a weaker result.

## Rationale

- **Difference alone** was rejected: without the sham, drift and handling are indistinguishable
  from a defect, and disc-06 drifts 2.5 % in a session.
- **Absolute alone** was rejected: a contact fault makes a defect-shaped trough at a fixed
  electrode, and that is exactly what disc-06 shows now.
- **Requiring both** cross-checks the two failure modes: a contact fault cancels in the
  difference, drift does not enter the absolute. A trough that shows in both, on the drilled
  angle, and not in the sham, has no explanation left except the hole.
- **±30°** is one electrode spacing; with 12 electrodes and a smooth JAC prior, a tighter
  window would claim resolution the instrument has not shown. **Significance 2.0** reuses
  ADR-0027 rather than inventing a new threshold.
- **Full-thickness, 20 % hole** because the solver is 2D and smaller targets are below the
  expected resolution; a smaller hole is tried only after a large one is seen.
- A second hole at E8 (~330°) moving the trough is stronger evidence but is optional, so that one
  disc can still give a result.

## Consequences

- Drilling cannot start until the E4 contact is fixed and B1–B3 pass absolutely. If E4 cannot
  be fixed, the claim is the weaker fallback, stated as such.
- Each attempt costs at least 7 runs (B1–B3, S1, D1–D3), about 50 minutes of capture.
- The claim is limited to one through-hole of about 20 % diameter in the usable sector,
  on one disc. It says nothing about E1–E3, blind holes, smaller holes, or living trees.
- A failed sham invalidates the attempt; the disc must be stabilised (cling film, shorter gap)
  and the protocol rerun, possibly on a new disc.
- Trough centroid and angle are read from the reconstruction (`tree_ert.reconstruction`,
  peak angle); no new code is required, but the angle convention (≈ (7 − n) × 30°) must be
  applied consistently.

## Verification

Unverified until the disc-06 session runs. The evidence is the recorded runs B1–B3, S1, D1–D3
under `scans/runs/`, their absolute gate results, their difference images against B3, and the
hole photograph and geometry in `Conditions.notes`. The criterion is falsified for this
instrument if the sham is non-empty, or if a through-hole of this size gives no trough in either
image.
