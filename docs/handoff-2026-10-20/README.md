# Handoff: proving the instrument can detect a hole in a coconut disc, 2026-10-20

For whoever runs the next bench session, operator or agent. Read `CLAUDE.md`, `AGENTS.md` and
`docs/handoff-2026-10-19/README.md` first; this covers what changed on 2026-10-20 and the plan to
reach one result: **a hole drilled into a disc shows up in the image, in the right place, above
the noise.**

## 1. Where the hardware stands

| Item | State on 2026-10-20 | Evidence |
|---|---|---|
| Open-circuit leak | **Mostly fixed.** 156 µA → frame median ≤0.3 µA after two IPA cleans and replacing corroded wires. A residual ~7–10 µA remains when driving E10/E11 (12–14 µA worst record at DAC 620). The leads add no leak. Accepted, with a per-session check. | `exports/open-circuit-2026-10-20/`, ADR-0066 |
| E1/E2 fault | **Not fixed.** Empty saline tank, all electrodes: misfit 60–61 % (3/3 refused); with E1/E2 excluded: 9–11 %. The flag stays on channels E1/E2 after swapping clips at the nails and leads at the terminal block. Terminal-to-mux resistance is 0.8–1.1 Ω on all paths checked, and no leak path to neighbours, rails or select lines. The current muxes behave normally; the sensed voltage on E1 is wrong on both sense muxes. Remaining suspect: inside the mux chips on C0/C1. | `scans/runs/20261020-1459*`…`1527*`, ADR-0064, ADR-0067 |
| Host | Raspberry Pi 5 gives the same results as the laptop. | `scans/runs/20261020-154712-saline-empty-rpi-*` |
| disc-06 | 7 baselines, **all refused** on misfit (36–40 % at DAC 400, 18–21 % at DAC 620). E4 flagged in every run (35–44 %, all-pair median 8–15 %), trough fixed at ~75° beside E4. Retightening E4 did not help. **Very repeatable:** σ0 5.78–5.95 mS, noise 0.37 %, current 461–468 µA at DAC 400. Not drilled yet. | `scans/runs/20261020-16*`, `-17*` |

Electrode angles in the images: **angle ≈ (7 − n) × 30°**, so E7 = 0°, E6 = 30°, E5 = 60°, E4 = 90°,
E1 = 180°, E10 = 270°, E8 = 330°.

Blind or biased sectors: **E1–E3 (120–180°) blind** under the E1/E2 exclusion; **E10–E12
(210–270°) slightly biased** by the leak. Usable: **E4–E9, about 300° through 90°**.

## 2. Goal: the hole in both the difference and the absolute image

Both are required:

- **Difference image** (after vs before, same disc, never remounted): the trough lands on the
  hole. Bad contacts cancel here, because they are identical before and after.
- **Absolute image** (after-drilling run alone): passes the ADR-0041 gates (misfit ≤15 %,
  reciprocity ≤15 %, significance ≥2.0) **and** shows the trough on the hole. The before-drilling
  absolute image must pass too, and show no trough in the drill sector.

**disc-06's absolute image fails because of the E4 screw contact alone.** Re-solving the
2026-10-20 runs:

| disc-06 run | E1/E2 excluded | E1/E2/E4 excluded | E1/E2/E7 excluded (control) |
|---|---|---|---|
| 163003, DAC 400 | 40.2 % | **2.4 %** | 42.4 % |
| 170539, DAC 400, E4 retightened | 36.1 % | **2.5 %** | 38.0 % |
| 171449, DAC 620 | 21.4 % | **2.1 %** | 24.2 % |
| 172458, DAC 620, 32 samples | 21.7 % | **2.2 %** | 24.6 % |

Dropping the healthy E7 changes nothing, so this is E4, not the loss of pairs. Excluding E4 as
well leaves only 30/108 pairs and blinds 60–180°. Use that only as a fallback (§5). The real fix is
a good E4 contact, which §3 step 1 does before anything else.

Repeatability is already good: σ0 within 2.7 % over 7 runs, noise 0.37 %.

## 3. Protocol: disc-06, drill and difference

Settings: adjacent, DAC 400, settle 10 ms, 16 samples, E1/E2 excluded, 5 warm-up + 10 frames
(about 7 minutes a run).

0. **Open-circuit check** with nothing attached (`exports/open-circuit-2026-10-20/open_circuit_check.py 1`).
   Go ahead only if the worst record is ≤20 µA and drives other than E10–E12 are ≤2 µA (ADR-0066).
1. **Fix E4 first.** Retightening did not work on 2026-10-20. In order, stopping when it works:
   a. remove the E4 screw, clean the hole and the screw (IPA, let it dry), refit it to the same
      depth as the others, apply gel;
   b. if E4 is still flagged: put a new screw in a fresh hole about 5 mm from the old one, at the
      same radius, and update the electrode positions in the notes;
   c. check with one short run (2 warm-up, 4 frames): E4's contact flag should be near the
      all-pair median, and misfit ≤15 % with only E1/E2 excluded.
2. Attach the leads. **From here on, do not touch the screws, clips or leads until the end.**
   Do not add or remove gel after this point. Wait 10 minutes for the contacts to settle.
3. **Baselines B1, B2, B3.** They must agree on σ0 within 2 % and on current within 2 %, and
   **pass the absolute gates with no trough in the drill sector.** If they don't pass, do not
   drill: go back to step 1.
4. **Sham (the false-positive control).** Wait as long as drilling will take (say 15 minutes),
   handle the disc the way drilling will (press on it where you'll drill, without drilling), then
   take **S1**. Difference S1 against B3. **This image must be empty** (significance <2, no trough
   in the drill sector). If it is not, drift or handling alone makes a "detection", and the result
   below cannot be trusted.
5. **Drill hole 1** without unclipping anything:
   - sector **E6, about 30°**, half way from the centre to the edge;
   - **through the full thickness** (the solver is 2D: a blind hole is a weaker, smaller target);
   - diameter about **20 % of the disc diameter** (for example 25 mm on a 125 mm disc). Smaller
     holes are below the expected resolution; go smaller only after a large hole is seen;
   - clear the chips, then photograph the disc with E1 marked. Record centre angle, radius
     fraction, diameter and depth in `Conditions.notes`.
6. **After-runs D1, D2, D3.** Difference each against B3 (Qt: "Load baseline from run…"; or
   `tree_ert.reconstruction.reconstruct`).
7. **Optional hole 2** at **E8, about 330°**, same size, then D4–D6. A second hole that moves the
   trough is much stronger evidence than one.

**Pass for the thesis claim (all of these):**

- **Difference:** D1–D3 against B3 each show a resistive (blue) trough whose centroid is within
  **±30°** of the drilled angle, with significance **≥2.0**, agreeing within about 15°.
- **Absolute:** B1–B3 pass with no trough in the drill sector; D1–D3 pass and their trough is
  within ±30° of the drilled angle.
- **Sham:** S1 against B3 is empty.

Write down what failed if it fails: a trough in the wrong sector is a result too.

## 4. Moisture: does wetting and drying help?

**Only with controlled conditioning. Never scan a disc with a wet surface.**

What the data says: discs at **σ0 about 2–6 mS** with stable contacts behaved best (disc-01, 06, 08).
Wet discs (σ0 6–14: disc-02, 03, 05) had poor reciprocity. Dry disc-10 (<1 mS, about 90 µA) is
below the ADR-0066 current floor. Water on the surface is a conducting skin that joins the screws
directly and bypasses the interior. It also evaporates during the scan, which is drift.

Steps for a disc that is too dry (σ0 <2 mS or current <300 µA):

1. Wrap it in a damp (not dripping) cloth, or mist it lightly, and put it in a sealed plastic bag.
2. Leave it **at least 12–24 h** so the moisture spreads evenly through the wood.
3. Take it out, pat the surface dry with a paper towel, and wait **15–30 minutes** until the
   surface looks matt (not shiny).
4. Weigh it and write the weight in `Conditions.notes`. Note σ0 from the first baseline.
5. Repeat until σ0 is in the 2–6 mS window.

For a disc that is too wet (σ0 >6 mS): leave it open to the air and check σ0 every few hours. Then
seal it in a bag for 12 h so the interior evens out before scanning.

During the before/after test, slow the drying: wrap the disc's rim and underside in cling film,
away from the screws. disc-06 lost about 2.5 % of σ0 over the 2026-10-20 session. That is a
uniform change, but it adds to the difference image, which is why the sham in §3 step 4 is required.

Contacts: the same gel on every screw, applied once, before the baselines. Re-seat a screw (remove,
clean, refit, gel) only **before** step 1 of §3, never between before and after.

## 5. If disc-06 fails

- **The sham shows a trough as well:** drift dominates. Shorten the gap between B3 and D1, wrap
  the disc (§4), and repeat on a fresh disc.
- **No trough after drilling and an empty sham:** the hole is too small or not through. Enlarge it
  (keep the centre), rescan.
- **E4 cannot be fixed (step 1 a–b both fail):** fall back to excluding E1, E2 and E4 for the
  absolute solve (misfit about 2 % on 2026-10-20, but 30/108 pairs, 60–180° blind). The E6 hole
  at 30° is still outside the blind sector. Report it as a weaker result and say why.
- **Trough appears but at E4 (~75°):** the E4 contact changed. Note it, re-seat E4, and start a
  new baseline before drilling again.
- **Next disc:** disc-02 or disc-03 after conditioning into the 2–6 mS window (§4). Avoid disc-04,
  07, 09 (unstable contacts, possible internal damage, decay).

## 6. Paperwork needed

- **ADR:** the detection criterion for disc holes: same-specimen difference **and** gated absolute
  image, both on the hole, plus an empty sham. Write it before drilling.
- **ADR:** the moisture-conditioning rule (2–6 mS window, sealed-bag equilibration, weigh and
  record).
- Fill in `Conditions.notes` for every run: contact method, gel, weight, hole geometry.

## 7. Still open, not blocking this test

- E1/E2: move them to the spare mux channels C12/C13 on all four muxes (8 wire moves and a firmware
  channel-map change, with a test and an ADR), or replace the chip. Then rerun the empty tank with
  all electrodes; the pass is misfit ≤15 %.
- The residual E10/E11 leak (ADR-0066).
- Current-source trim (handoff 2026-10-19 §3.2).
- Untracked `docs/weekly-reports/` on the laptop: review before committing.
