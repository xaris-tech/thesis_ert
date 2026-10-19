# Handoff: ERT absolute-reconstruction validation, 2026-10-14 to 2026-10-19

For a fresh agent picking up the Phase 3A tree-ERT rig in `D:\Here\asd`. Read the repo's
`CLAUDE.md` and `AGENTS.md` first; this document covers only what the last sessions
learned and what is left to do.

## 1. State of the repo

- Branch `new` (checked out) = `origin/new` = `161e467`. Nothing uncommitted. Branch `ssim`
  is older (`c061e33`); `new` contains all of it. `main` was not touched.
- New this period:
  - `docs/adr/0064-exclude-faulty-channels-from-the-absolute-solve.md`: the
    `UiSettings.absolute_exclude_electrodes` setting, the Qt "Absolute: exclude" field, and
    `absolute.exclude_electrodes`.
  - `docs/adr/0065-absolute-colour-matches-difference-images.md`: absolute images use
    `coolwarm`, blue less conductive and red more. All 2026-10-14 absolute PNGs were
    re-rendered.
- All runs are in `scans/runs/2026101[4-9]-*`, each with its own `conditions.json`,
  `frames.csv`, `summary.txt` and `absolute.png`, and listed in `scans/index.csv`. The commit
  messages for 3609525..161e467 hold the per-session numbers.
- Exports, all committed:
  - `exports/saline-absolute-2026-10-14/`: the saline position series, `summary.csv`, and
    difference images against no-wood.
  - `exports/disc-01-absolute-2026-10-14/`, `exports/disc-05-absolute-2026-10-14/`
  - `exports/disc-holes-vs-disc-02/` and `exports/disc-holes-vs-disc-02-exclE1E2/`
  - `exports/disc-08-vs-disc-02-exclE1E2/`
  - `exports/dummy-load-20261014.csv`
- **The tooling used is not a repo CLI yet.** Copies are in `docs/handoff-2026-10-19/scripts/`:
  - `saline_matrix.py`: the matrix runner. Takes `--patterns --dacs --settles --samples
    --exclude --medium --specimen --target --label --notes --start`, and records like a Qt
    run.
  - `resolve_all.py`: re-solve recorded runs with all electrodes.
  - `drop.py`: misfit with E1/E2, E1–E3 or E5/E6 dropped.
  - `compare_excl.py`: difference images against disc-02, with E1/E2 excluded.
  - `collect.py`: builds the saline export folder.

  The scripts hard-code some paths. Worth turning `saline_matrix.py` into a repo tool, with
  an ADR, if matrices continue.

## 2. Findings

### 2.1 Hardware

| Fault | Evidence | Effect |
|---|---|---|
| **Current source is load-dependent** | Dummy-load sweep: ring 202 Ω vs ring + 1 kΩ in series gives Rout ≈ 770 Ω at every DAC code, flatness 69 %, 154 mV output at DAC 0. Resistors R1 4.984k, R2 98, R3 5.015k, R4 100.0 give a 1.4 % ratio mismatch, which predicts Rout ≈ 720 Ω. Pin-5 wiring was re-checked and is correct (ADR-0014 repair intact). | Current falls on high-resistance loads (dry disc-10: about 90 µA). Readings stay valid because each is divided by its measured current, but the signal shrinks and contacts polarise. |
| **E1/E2 board channels faulty** | The contact flag stays on channels E1/E2 after swapping nails 1↔12 and 2↔3. Excluding them takes saline misfit from 56–67 % to 10–13 %. Dropping a healthy pair (E5/E6) changes nothing. | With all electrodes, **0/30 saline runs pass** and the trough sits on E1 (~180°) even in the empty tank. |
| **Open-circuit leak** (2026-10-19) | Nothing connected, harness still on: 156 µA at DAC 620 and 49 µA at DAC 100, every record marked OK. On 2026-09-22 the same test gave 0.8 µA. Leak is highest when driving E9–E11 (198–203 µA, against 145–158 on the others). | Biases high-impedance loads. Prime suspect for the fixed trough at E9/E10 on several discs. It is not yet known whether it is in the harness or on the board. |
| Resistor-ring check | 2026-10-19: 831 µA at DAC 400, 18.1 Ω, reciprocity 0.07 % median. Same as 2026-10-14. | The chain is fine on low-resistance loads. The ring cannot see the leak. |

### 2.2 Saline tank (2026-10-14, adjacent, nail electrodes, tank unmeasured: "pinch of salt", ~50 mm)

- **With E1/E2 excluded:** 28/29 runs pass. Wood found at E4, E6, E8 and E10 within 2–9° in
  the absolute image, and 2–7° in the difference image against no-wood. Repeat runs agree to
  within about 1°. Best setting: DAC 620 (or 400), settle 10 ms, 16 samples.
- **With all electrodes:** 0/30 pass. The saline result **depends on the exclusion**, and the
  thesis must say so. The 120–180° sector (E1–E3) is blind under exclusion.
- Shorter settle is always better (10 ms beat 30 and 50). σ0 depends on settle time, so only
  compare σ0 at equal settings. A fixed high spot near E7 (~0°) and a weak trough at E8 appear
  even with no wood.
- Opposite and skip patterns give no reciprocal pairs, so the reciprocity gate cannot pass on
  them as the gate is written (ADR-0041).

### 2.3 Discs (adjacent, all-electrode verdicts unless stated)

| Disc | State | Result | Notes |
|---|---|---|---|
| disc-06 | intact outside | **6/6 pass at DAC 400** (misfit ≈ 4 %, reciprocity ≈ 1 %, σ0 6.1–6.2 mS, current even on all screws) | Around 10:00 on 2026-10-19, after the first DAC 620 run (about 1160 µA), current halved and runs 8–14 failed, with E3/E4 flagged. The operator says nothing was touched. Most likely high current changed the screw contacts. The trough touches E3/E5 even in the passing runs. |
| disc-01 | holes near E4–E7 | 12/12 pass (2026-10-14) | Trough at E10 (271°) in every run, so the holes are missed. |
| disc-02 | intact | 0/14 with all electrodes; 13/14 with E1/E2 excluded | Wet (σ0 6–8 mS). E2 screw was tightened mid-run 8. Trough at E10 (269°) in every run, which matches disc-01, so it's an artefact. |
| disc-05 | hole between E1–E2 | refused with all electrodes; passes with E1/E2 excluded | Drying during the session (σ0 9.1 → 7.0). The hole sits in the excluded sector, so it can't be tested. An earlier 165° "probable hit" in the difference image was withdrawn: it can't be separated from the E1/E2 fault. |
| disc-08 | hole near E9–E11 | 0/14 (misfit 37–39 % at DAC 400, 18–21 % at DAC 620; reciprocity passes) | Dry (σ0 ≈ 2.6). Difference image against disc-02 puts the trough at 323°, 23° outside the hole sector, next to the flagged E9. Suggestive, not a detection. |
| disc-03 | intact | 0/14 | Wet (σ0 8–14). E2, then E3, flagged. Still fails on reciprocity with E1/E2 excluded. |
| disc-04 | intact outside | 0/14 | Reciprocity 40–77 %. σ0 and current swing between runs (130 → 334 µA at the first DAC 620 run). Unstable contacts. |
| disc-07 | intact outside, interior unknown | 0/14 | Misfit 84–92 % whatever the setting, so a possible internal defect. DAC 620 made reciprocity worse (up to 57 %). |
| disc-09 | intact outside, fungal growth | 0/14 | Reciprocity 29–57 %, misfit 70–87 %. Decay. |
| disc-10 | intact, light | 0/14 | Too dry: σ0 0.7–0.9 mS, current 87–136 µA, screw currents 50 µA (E1, E2, E3, E12) to 350 µA (E8, E9). |

### 2.4 Cross-cutting conclusions

1. **Gates passing ≠ a correct image.** disc-01 and intact disc-02 both pass with the same
   E10 trough. The gates test internal consistency, not truth.
2. **Settings are not the bottleneck.** 14-run matrices (DAC 400/620 × settle 10/30/50 ×
   samples 16/32) barely change verdicts. Contacts, moisture and the board faults decide.
3. **Moisture window:** σ0 around 2–6 mS with stable contacts behaved best (disc-01, 06, 08).
   Wet discs (6–14) and dry discs (<1) both fail.
4. **Long DAC 620 runs degraded two discs (06, 07).** Prefer DAC 400 on wood.
5. **Troughs that touch an electrode** are usually contacts, leak or channel faults, not wood.
6. **Cross-specimen difference baselines confound** specimen differences with defects.

## 3. What needs doing, in order

### 3.1 Find and fix the leak and the E1/E2 fault (blocking everything)

1. **Locate the leak.** Unplug the electrode harness at the board header, so only the board
   is left, and run the open-circuit check: one frame at DAC 620 and one at DAC 100, settle
   10, 16 samples, `lenient_quality=True`, reporting per-drive-electrode median current.
   - About 0 µA: the leak is in the harness. Then clean the connector and lead ends with IPA,
     check insulation (especially the E9–E11 leads), dry, and retest with the harness on and
     nothing clipped.
   - Still about 150 µA: the leak is on the board. Go to step 2.
2. **Clean the board:** IPA plus a brush on the CD74HC4067 mux pins and headers, especially
   the E1/E2 and E9–E11 channels. Inspect for solder bridges and flux, which is likely on
   perfboard. Dry fully, retest open-circuit, and keep going until it reads ≲1 µA. If it won't
   clear, suspect a mux chip damaged by overvoltage: the source can swing about ±9 V into a
   3.3 V mux when the load is open or dry. See
   `docs/first-working-prototype/10-safety-and-troubleshooting.md`.
3. **Re-verify E1/E2:** repeat the nail-swap test in saline, then rescan saline **with all
   electrodes**. Pass criterion: misfit ≤15 % without exclusion. Once it passes, stop using
   `absolute_exclude_electrodes`, and write an ADR superseding ADR-0064's reliance on it.
4. **Make the open-circuit check routine** at the start of every session. It could be a
   self-test item in `tree_ert/selftest.py`.

### 3.2 Current source (important, not blocking)

- Raise R1 slightly against R4/R3 by putting about **360 kΩ in parallel with R1** (pin 2 to
  GND); a trimmer is better. Come at the matched point from the under-corrected side:
  overshooting gives positive feedback and oscillation.
- Verify with `dummy_load_sweep.py measure` (ring alone, then ring + 1 kΩ in series in the E1
  lead) followed by `fit`. Target: flat current, Rout ≫10 kΩ. Then re-check the 154 mV DAC-0
  offset. Write an ADR (ADR-0013 open item).
- The operator could not fit the resistor this time. It's still open.

### 3.3 Disc protocol: same-specimen before/after drilling (the decisive test)

Cross-specimen baselines don't work, so use one disc and never remount it:

1. Mount the disc, apply the contact treatment (§3.4), and wait about 10 minutes for it to
   settle.
2. Run 3 runs at **DAC 400, settle 10 ms, 16 samples** (about 4 minutes each), all electrodes.
   They must pass, and agree on σ0 within about 2 %.
3. **Drill a hole without unclipping the leads.** Place it in a sector away from E1–E3 and
   E9–E11 until those channels are cleared: the E5–E7 sector, around 0–60°, is safest.
   Record the position and depth, with a photo, in conditions.
4. Run 3 runs again. Make a **same-specimen difference image** (Qt "Load baseline from run",
   or `tree_ert.reconstruction.reconstruct`), plus an absolute image.
5. Optionally drill a second hole in a different sector and repeat.
6. Pass: the trough lands in the drilled sector, significance ≥2, and the 3 repeats agree.

**Candidate discs, best first:**

| Rank | Disc | Why | Prep needed |
|---|---|---|---|
| 1 | **disc-06** | Only disc that passed with all electrodes; even contacts; σ0 ≈ 6 | Re-seat or gel the E3–E5 screws; keep to DAC 400; short sessions |
| 2 | disc-02 | Intact; passes 13/14 with E1/E2 excluded | Dry it first (σ0 was 6–8); E2 already tightened; gel |
| 3 | disc-03 | Intact | Dry (σ0 8–14); re-seat E3; gel |
| 4 | disc-10 | Intact, very uniform wood | **Must have gel on every screw** (too dry, 90 µA). Or condition it to the same moisture as the others |
| — | disc-04, disc-07, disc-09 | Unstable contacts / possible internal damage / fungal decay | Unsuitable as before/after specimens. Disc-07 could instead be split or cut open to check whether its interior explains the 84–92 % misfit |
| — | disc-01, 05, 08 | Already holed, no intact baseline | Use only after the board fix. Rotate disc-05 a quarter-turn so its hole sits away from E1/E2 |

### 3.4 Contact treatment (gel / conditioning)

- **Needs gel on every screw:** disc-10 (dry); disc-04 and disc-09 (unstable contacts); and
  the before/after disc, so contacts stay constant across the drilling.
- **Needs drying first:** disc-02, disc-03, disc-05 (σ0 >6 mS, poor reciprocity).
- Better still, **condition every disc to the same moisture** (for example a set time in a
  sealed bag or with a damp cloth) and record weight or moisture in `Conditions.notes`. Aim
  for σ0 of about 2–6 mS.
- Record the treatment in conditions every time. Most of these runs say "contact method not
  stated".

### 3.5 Saline series (deferred by the operator)

Planned: empty baseline (first **and** last), wood at each of E1–E12, pairs 1+7, 2+8, 3+9,
4+10, 5+11, 6+12, and centre. 3 runs each at DAC 400 / settle 10 / 16 samples. That's 63 runs,
about 4.4 h machine time plus about 20 position changes. **Do it after §3.1**, so it's valid
with all electrodes; otherwise E1–E3 positions are blind. Measure the saline g/L, water
temperature and fill depth, so σ0 can be checked against a true value.

### 3.6 Software follow-ups

- Promote `docs/handoff-2026-10-19/scripts/saline_matrix.py` to a repo CLI (for example `matrix_session.py`), with a
  test and an ADR.
- Complete-electrode-model contact impedance in `tree_ert/absolute.py`, so contact
  differences are modelled instead of imaged as electrode-adjacent troughs. Write an ADR.
- Reciprocity gate for opposite and skip patterns (no reciprocal pairs today).
- Consider a gate or warning when the trough touches an electrode on a specimen expected to
  be intact.

### 3.7 Housekeeping

- **Laptop power settings changed on 2026-10-14 and not restored:** battery standby set to
  0 (never), lid action set to "do nothing" (unverified). Windows Update pause has expired.
  Restore with `powercfg /change standby-timeout-dc <minutes>` and the lid-action index on
  `SUB_BUTTONS LIDACTION`, but ask the operator first.
- GitHub pushes from this machine need the operator to approve a Git Credential Manager
  sign-in. `git push` can hang waiting for it.
- Board serial port is COM7. The Qt UI must be closed while scripts use the port.

## 4. Suggested skills

- `mattpocock-skills:diagnosing-bugs`: localising the open-circuit leak and the E1/E2 / E10
  channel faults (§3.1).
- `mattpocock-skills:domain-modeling`: the ADRs this work needs (superseding ADR-0064 once
  E1/E2 is fixed, the before/after drilling protocol, the moisture-conditioning rule, the
  current-source trim).
- `mattpocock-skills:tdd`: promoting the matrix runner and adding an open-circuit self-test
  or contact-impedance model with tests first.
- `mattpocock-skills:code-review`: before merging `new` into `main`.
- `artifact-design` / `dataviz`, if a supervisor-facing summary page of these results is
  wanted.
