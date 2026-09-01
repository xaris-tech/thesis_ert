# Validity Audit — Phase 3A

Independent review completed 2026-08-27 against the working tree of that date.

This document records what was checked, what was found broken, and what was confirmed
correct. It is a findings record, not a work queue — agreed-but-unimplemented work lives in
[planned-improvements.md](planned-improvements.md), and the open task list in
[TODO.md](../TODO.md). Canonical current behaviour stays in [AGENTS.md](../AGENTS.md) and
[HANDOVER.md](../HANDOVER.md).

Finding IDs (`D-*`, `L-*`, `X-*`) are stable; cite them when fixing or disputing an item.

## Status, updated 2026-08-27

Fixed and covered by tests: **D-01, D-02, D-03, D-04, D-05, X-04 (polarisation
flag)**. **X-03** is addressed the way this section itself recommends — stated plainly, not
built out — via a module docstring on `tests/test_phase3a_unified_firmware.py` and a
CLAUDE.md note; there is still no compiled/behavioural firmware test in this repo, and
building one (toolchain + simulator or hardware-in-loop) remains a real, unstarted project,
not something this pass attempted. `tests/test_reconstruction_localisation.py` is the forward-model test recommended in
section 6 — it puts a target of known angle and known sign through the pipeline and asserts
both, which is what would have caught D-01 and D-02.

Two notes on how the fixes differ from the recommendations:

- **D-03 was resolved by dropping the absolute arm, not by AND-ing it.** AND-ing fails
  legitimate baselines: 1 percent drift on a 2 kOhm signal is already 20 ohm absolute, far
  past the 2 ohm threshold. The value is still computed and reported for diagnostics, but no
  longer decides stability. Confirmed by test: a real-signal baseline that exceeds the
  absolute threshold is now stable, and a near-zero offset-dominated baseline is not.
- **D-05 is now fully addressed.** Substituted pairs are still rendered on the figure with
  their count, percentage, and quality label, so a substituted null cannot be read as a
  measured one. In addition, `reconstruct_difference()` (`phase3a_reconstruct.py`) now accepts
  `dropped_indexes` and, when given, excludes those rows from both the frame-scaling factor `a`
  and the backprojection sum — `dv[dropped] = 0` against `solver.H` rather than relying on
  `filtered - baseline ≈ 0` to make the residual merely small. Both capture paths
  (`phase3a_unified_reconstruct.py`'s CLI loop and `tree_ert/controller.py`'s
  `capture_target`) pass `filtered.dropped_indexes` through.

Still open: **L-01, L-02, L-03, X-01, X-02**, and the
`MIN_VALID_CURRENT_UA` / `FIRMWARE_MIN_CURRENT_UA` duplication in X-04.

### Confirmed on hardware, 2026-08-27

The board was reflashed and probed on COM7 against the saline tank at `p75 t10 n16`, HIGH
range. Results against the pre-fix figures in `planned-improvements.md` section 1.2:

| Metric | Before | After F1 |
|---|---:|---:|
| Worst polarisation decay | 39.15x | **1.17x** |
| Flagged injection groups | 22/24 | **0/24** |
| Minimum frame current | 5.469 uA | **126.2 uA** |
| Median frame current | 43.9 uA | **753.5 uA** |

Record polarities arrive `FWD, REV, FWD, REV`, confirming the interleaving. Median current
rose roughly 17x at a *lower* DAC code, which is the current that polarisation had been
consuming.

The offset check did **not** improve (102/108, was 101/108), and the probe showed why: every
flagged voltage was an exact multiple of the 125 uV `GAIN_ONE` step, with the worst pairs
reading identical forward and reverse values (`fwd=+60.000 mV`, `rev=+60.000 mV`,
`differential=0.000 mV`). The pairs that did invert were the high-signal ones. So the residue
was quantisation, not polarisation, and D-04's averaging fix was inert because all 16 samples
returned the same count. That produced F8 (electrode-voltage PGA autoranging) in
`planned-improvements.md`.

F8 itself is **not yet verified on hardware** — it needs another flash.

## Scope and evidence level

- Host-side findings were **reproduced** by running the project's own functions
  (`assess_baseline_stability`, `build_adjacent_protocol`, `create_solver`) against PyEIT's
  forward solver. The quoted figures are deterministic and re-runnable.
- Firmware findings are from **source reading only**. The board had not been reflashed since
  the last firmware change, so nothing here is confirmed on live hardware.
- External claims are cited in [Sources](#sources).

Summary: 5 confirmed defects, 3 architectural limits, 6 core assumptions verified correct,
4 documents contradicting the code.

---

## 1. Confirmed defects

Ranked by how much each distorts a conclusion a reader would draw. None of these produce an
error, a warning, or a failing test.

### D-01. Electrode labels on every reconstruction are mirrored against the mesh

**Location:** `phase3a_unified_reconstruct.py:758`, `phase3a_reconstruct.py:297`,
`tree_ert/ui.py:580`

All three plotting sites place the label `E{index + 1}` at angle `2 * pi * index / 12` — E1
at 0 degrees, running counter-clockwise. PyEIT's `mesh.create(n_el=12)` places electrode 0 at
180 degrees and runs **clockwise** in 30-degree steps. The image data is drawn in correct mesh
coordinates; only the annotation is wrong. The net effect is a reflection about the vertical
axis.

```text
reproduced: pyeit forward model, conductive inclusion at +30 deg, r=0.6

  peak reconstructed at (+0.54,+0.31) = +30.0 deg      correct
  solver-mesh electrode nearest that point: index 5 (E6) at +30.0 deg
  plot draws E6 at +150.0 deg                          wrong
```

Mirror pairs: `E1<->E7`, `E2<->E6`, `E3<->E5`, `E8<->E12`, `E9<->E11`. Fixed points: `E4`
(90 deg), `E10` (270 deg).

A hotspot genuinely at the solver's E6 is labelled E2 — four electrode sectors away, against
the success criterion in `HANDOVER.md` of "within 1-2 electrode sectors". This does not make
the validation test fail cleanly. It makes a correct localisation look wrong, or invites a
wrong one to be rationalised.

**Fix:** derive label positions from `eit_mesh.node[eit_mesh.el_pos]` rather than recomputing
an assumed angle. That removes the assumption instead of correcting it in three places.

### D-02. Reconstruction sign is globally inverted against the measurement convention

**Location:** `phase3a_reconstruct.py:145` versus firmware `readVoltageMv()` (ADS A0-A1)

`build_protocol` stores each measurement row as `[vn, vp]`, and PyEIT's `subtract_row`
computes `v[meas[:, 0]] - v[meas[:, 1]]`, so the forward model expects `V_vn - V_vp`. The
firmware measures the ADS1115 differential A0-A1, which is `V_vp - V_vn` — the negative.
Every entry in the vector carries the flipped sign.

```text
same conductive inclusion (perm 10 vs background 1):

  PyEIT convention      peak value  +0.6643    conductive -> red
  firmware convention   peak value  -0.6643    conductive -> blue
```

Localisation is unaffected; the peak lands in the right place either way. What inverts is the
colour: a more conductive target currently renders blue. The instruction in `HANDOVER.md` not
to read red as decay is good advice, but the polarity is not ambiguous as that note implies —
it is deterministically backwards and can be fixed.

**Fix:** swap to `[vp, vn]` in `build_protocol`, **or** negate `voltage_mv` at parse time. Not
both. Whichever side changes, `tests/test_phase3a_reconstruct.py` needs the matching
assertion.

### D-03. A baseline with no signal in it passes the stability gate

**Location:** `phase3a_unified_reconstruct.py:967-968`

The gate is `stable_by_relative_shape or stable_by_absolute_drift`, and the absolute arm is a
flat 2 ohm (`MAX_BASELINE_ABSOLUTE_RMS_KOHM = 0.002`). When the rig is offset-dominated — the
failure mode in `planned-improvements.md` section 1.3, where forward and reverse voltages fail
to invert — `paired_transfer_resistance()` collapses toward zero, and a vector of near-zeros
trivially clears a 2 ohm absolute threshold. The shape arm correctly fails; the `or` swallows
it.

```text
reproduced via assess_baseline_stability(), 10 frames, 108 pairs

  A  offset-dominated, no signal
     relRMS 305.3%   corr +0.183   absRMS 0.000951 kOhm   stable=True
  B  healthy rig, identical noise
     relRMS   0.091%   corr +1.000   absRMS 0.000947 kOhm   stable=True
```

The same threshold acts as a hidden current gate in the other direction. One ADS LSB expressed
as transfer resistance:

| Drive current | kOhm per LSB | Absolute gate on noise alone |
|---:|---:|---|
| 300 uA | 0.00042 | passes |
| 100 uA | 0.00125 | passes |
| 30 uA | 0.00417 | fails |
| 10 uA | 0.01250 | fails |

Identical data passes or fails purely on drive level.

**Fix:** make the gate `and`, or drop the absolute arm. It is a current-level proxy wearing the
costume of a quality check.

### D-04. Sample averaging buys no resolution — the mean is truncated to whole ADC counts

**Location:** firmware `esp32s3_phase3a_unified.ino:184-186`

```cpp
const int16_t averageCounts = static_cast<int16_t>(
    static_cast<float>(totalCounts) / sampleCount);   // <- truncates
return ads.computeVolts(averageCounts) * 1000.0f;
```

`readAveragedDifferentialMv()` sums `sampleCount` readings into a `long`, divides in floating
point, then casts back to `int16_t` before calling `computeVolts()`. The fractional part —
the entire point of averaging — is discarded. Output granularity stays at exactly one LSB no
matter what `n` is set to.

This is not academic. TI notes ADS1115 noise rises steeply with data rate, and the firmware
runs at the noisiest setting, `RATE_ADS1115_860SPS` (line 497), so there is real dither to
average against and `n16` should deliver roughly a 4x improvement. It delivers none.

Corroborating fingerprint in our own bench data: every voltage in `planned-improvements.md`
section 1.3 (10.000, 46.000, -28.000 mV) is an exact multiple of the 125 uV GAIN_ONE LSB.

**Fix:** scale the float mean by the LSB size rather than re-quantising it to an integer count.
Every capture taken so far is affected.

### D-05. The best-effort filter invents measurements rather than dropping them

**Location:** `phase3a_unified_reconstruct.py:368`, and `fill_missing_values()` at `:290`

When a pair is judged unstable the filter writes the **baseline** value into the target vector.
That is not exclusion — it is the assertion "nothing changed here", handed to the solver as
though it were measured. Since `solve_gs` works on `v1 - a * v0`, those entries contribute a
near-zero residual, actively pulling the reconstruction toward no-change in precisely the
regions where the data was too bad to trust.

The bias is toward a clean-looking null result, which is the most dangerous direction for a
decay-detection instrument. Up to 25 percent of pairs can be substituted before the run is even
labelled `debug-low-confidence` (`MIN_RECON_KEPT_PAIR_RATIO = 0.75`).

**Fix:** drop the rows from the inverse problem. If rebuilding the Jacobian is impractical, at
minimum render the substituted fraction on the image itself so a null result cannot be read as
a measurement.

**Status:** done. `reconstruct_difference(..., dropped_indexes=...)` zeroes the dropped rows'
contribution to both the frame-scaling factor and the backprojection sum, rather than the
Jacobian itself (rebuilding per-frame Jacobians for a fixed mesh/protocol is not something
`pyeit.eit.jac.JAC` supports without re-running `setup()`, which is per-protocol, not
per-frame). The image annotation from the first pass is unchanged and still shown alongside.

---

## 2. Limits that cannot be tuned out

Properties of the architecture as built. No firmware or host change reaches these; each needs a
hardware decision.

### L-01. The 3.3 V mux rail caps drive voltage an order of magnitude below the reference instrument

**Location:** `HANDOVER.md` ("mux analog signals must stay inside the mux supply range"),
`MAX_MUX_VOLTAGE_MV = 3000` at `.ino:15`

Current reaches the sample through `MUX_I_SRC` and returns through `MUX_I_RET`, both
CD74HC4067 parts powered from 3.3 V. Analog signals through an HC-series switch must stay
within its rails, so 3.3 V is the ceiling on electrode-to-electrode drive — hard, and
independent of the Howland source, the DAC, and the range jumper. Delivered current is bounded
at roughly `3.3 V / R_tree`.

| Inter-electrode resistance | Ceiling on delivered current | Verdict |
|---:|---:|---|
| 10 kohm | 330 uA | workable |
| 30 kohm | 110 uA | marginal |
| 100 kohm | 33 uA | below our own usable floor |

(Mux Ron plus the 97.9 ohm shunt is roughly 350 ohm — negligible against these loads.)

`HANDOVER.md` puts the usable floor near 100 uA and describes 14 uA as producing "mostly
random" reconstructions. **The deciding number has never been measured.** Two nails and a
multimeter on one coconut palm settles whether this is a footnote or a redesign.

If it turns out to be a redesign, the direction is a higher mux rail (CD74HCT4067 accepts 3.3 V
logic at a 5 V supply) or a higher-voltage analog switch family — not a firmware change.

### L-02. The current source's output impedance is comparable to its intended load

**Location:** `planned-improvements.md` section 1.1,
`docs/first-working-prototype/03-howland-current-source.md`

The bench finding — `Rout + Ron ~= 430 ohm`, current tracking `1/R_load`, constant-voltage
behaviour — is externally corroborated. The standard Howland result is that output impedance
degrades as roughly `R / mismatch`, and TI's own analysis notes even 0.1 percent parts can fall
short for precision work. At `Rs = 10 ohm` with ordinary-tolerance resistors, ~430 ohm is what
theory predicts. The section 1.1 diagnosis stands.

One addition to that write-up: rebuilding with the specified 0.1 percent parts would **not**
fix the HIGH range. At 0.4 percent worst-case mismatch, `Rs = 10 ohm` still gives only
~2.5 kohm — the same order as a tree. The LOW range (`Rs = 68 ohm`) reaches ~17 kohm. Treat the
design document's "start on LOW" as permanent, not a bring-up step.

### L-03. Voltage and current for one measurement are not sampled at the same time

**Location:** firmware `.ino:241-242`

```cpp
const float currentUa = readCurrentUa();
const float voltageMv = readVoltageMv();
```

Each call switches PGA gain and takes `n` conversions, so at `n16` the two channels are
separated by roughly 35 ms. Against the polarisation decay measured in
`planned-improvements.md` section 1.2 — current halving within a few successive readings — the
`V` and `I` in one `V/I` ratio describe different moments of the same transient.

**Cheap mitigation:** read current, then voltage, then current again, and divide by the mean of
the two current readings. Bounds the error instead of ignoring it, at the cost of one extra
conversion block.

---

## 3. What checks out

Verified independently rather than taken on trust. Several of these are the parts most likely
to be doubted in a defence.

| Item | Finding |
|---|---|
| Protocol construction | Matches PyEIT's own `protocol.create` convention exactly, including the `[N, M]` row order and the 108-measurement count for 12-electrode adjacent drive. |
| Transfer-resistance algebra | `0.5 * (R_fwd - R_rev)` cancels a static half-cell offset correctly, given equal forward and reverse current magnitudes. |
| Current-range table | `I = V_DAC * 0.02 / Rs` checks out at all three ranges: codes 420/680/620 give 99.6 uA, 498 uA, 999 uA against the stated 100 uA, 500 uA, 1.0 mA. |
| Break-before-make switching | `configureDriveAndSense` zeroes the DAC and disables all muxes before any address line changes. Order is correct. |
| Polarity interleaving (F1) | Matches how commercial tree ERT works — the reference instrument applies DC with alternating polarity in sub-second pulses for the same reason. |
| Difference imaging as the method | The EIT literature names difference imaging as the standard mitigation for exactly the unknown-boundary problem a tree trunk presents. The core methodological choice is defensible. |

---

## 4. Against the reference instrument

The PiCUS TreeTronic is the established device for this measurement, and the closest published
study — ERT on queen palm trunks — used 12 electrodes, the same count as this rig. The
comparison is unusually direct.

| Parameter | PiCUS TreeTronic (published palm study) | Phase 3A prototype | Gap |
|---|---|---|---|
| Electrodes | 12, equidistant | 12, equidistant | matched |
| Drive voltage | 12-50 V (device to 100 V) | 3.3 V ceiling | **4-15x** |
| Drive current | 3-10 mA | 0.1-1.0 mA design; 14-338 uA seen | **10-100x** |
| Polarity | alternating, pulse under 1 s | alternating, interleaved per pair | matched |
| Electrode | zinc-galvanised nail, 2-3 mm | screws / nails / alligator clips | contact unquantified |
| Imaging | apparent resistivity, 2D/3D | difference only | by design |

Two points from that literature bear directly on the thesis.

**The palm result is encouraging.** Palms lack heartwood, which removes the single most-cited
limitation of tree ERT — the difficulty of characterising defects in dry heartwood. Coconut is
in the same family, so the target species is a better fit for this method than a typical dicot
would be. The study visualised damage from both *Ganoderma zonatum* and *Fusarium oxysporum*
f. sp. *palmarum*.

**Healthy-palm baselines at the same site are essential.** The same study found irrigation
status dominates the water-content pattern in healthy specimens. With three trees and no
healthy-baseline library, that is the interpretive constraint most likely to be raised in a
defence — and it is a sampling-design point, not something more careful electronics answers.

On the reconstruction side, the isotropic circular mesh is a real but accepted simplification:
wood is anisotropic, anisotropy-aware EIT algorithms exist but are not practically available,
and difference imaging is the recognised way to live with it. Worth stating explicitly in
Chapter 3 rather than leaving implicit — a known limitation with a literature to cite is a much
stronger position than an unexamined assumption.

Note also that `--diameter-cm` is a label only; the mesh remains a unit circle, so no
reconstruction output is in real centimetres.

---

## 5. Documents that contradict the code

### X-01. The validation runbook fails its own checks against current firmware

**Location:** `docs/current-setup-validation-runbook.md`

It instructs the reader to confirm `SHUNT_OHMS,100.0` (firmware now defaults to 97.9) and
MCP4725 at `0x60` (firmware uses `0x61`, and the hardware answers there — see F3/D2 in
`planned-improvements.md`). It also gives macOS paths (`/dev/cu.*`, `.venv/bin/python`) in a
Windows/COM-port project. This is the document that gates "before trusting any reconstruction
image", so an operator following it exactly stops at step 2 on a correctly working rig.

**Status:** reconciled at the doc level — shunt value, I2C addresses, and Windows/PowerShell
paths and commands (`Get-PnpDevice`, `.\.venv\Scripts\python.exe`) now match the firmware and
`CLAUDE.md`. Steps 0 (test suite) and the command syntax were re-verified this pass. Steps 1-6
and 8 (serial detection, I2C scan, dummy-load current sweep, mux path check, single-frame
check) were **not** re-run end to end because doing so requires a connected ESP32-S3 and bench
multimeter, which this pass did not have. Re-running those against real hardware before relying
on this runbook again is still outstanding.

### X-02. Chapter 3 states an AIoT pipeline that has no implementation

**Location:** `docs/chapter-3-methodology-draft.md`

The methodology states the system stores data locally on a Raspberry Pi and synchronises to
Google Drive. No Raspberry Pi, Drive, or classifier code exists anywhere in the repository. The
classifier is correctly flagged as future-facing; the storage and sync path is written as
present-tense method. Either build it or move it into the same future-work framing before
submission.

### X-03. Firmware tests assert source text, so no test can fail on behaviour

**Location:** `tests/test_phase3a_unified_firmware.py`

Every assertion is a string or regex match against the `.ino`. That is a legitimate doc/code
sync guard and worth keeping, but nothing in the repository compiles the firmware, and no test
could have caught D-04. Worth stating plainly wherever verification is described, so the test
count is not read as behavioural coverage.

**Status:** stated plainly — module docstring added to `tests/test_phase3a_unified_firmware.py`
and a matching note in `CLAUDE.md`. Building an actual compiled/behavioural firmware test
(PlatformIO + a HAL-level simulator, or hardware-in-loop against a real board) is not done and
is a materially larger effort than the rest of this list; treat it as a separate project.

### X-04. Three smaller inconsistencies

**Location:** `phase3a_unified_reconstruct.py:23`, `:38`, `:533`

- `MIN_VALID_CURRENT_UA = 0.5` is unreachable. The firmware flags `I_LOW` at 1.0 uA first, and
  `record_is_valid` requires `quality == "OK"` anyway.
- `FIRMWARE_MIN_CURRENT_UA = 1.0` duplicates a firmware constant with no sync mechanism.
  Planned item F6 (runtime-configurable quality thresholds) breaks this the moment it lands.
- `analyze_polarization` computes `decreasing_fraction` but flags purely on `decay_ratio`, so a
  noisy non-monotonic pair can be reported as polarisation despite the docstring specifying
  monotonic decay.

---

## 6. Recommended order

Deliberately not the order in `planned-improvements.md`, because two of these change what
"working" means.

1. **Measure two-nail resistance on an actual coconut palm.** Five minutes with a multimeter.
   Determines whether L-01 is a footnote or a redesign, and every other decision is cheaper once
   it is known. Do this before any more software work.
2. **Fix D-01 and D-02, then write the test that would have caught them.** A forward-model test
   with an inclusion at a known angle, asserting both peak position and sign. There is currently
   no test anywhere that puts a known target through the pipeline and checks where it lands —
   which is why both defects survived.
3. **Fix D-04.** A two-line change that recovers the resolution the averaging setting has been
   promising all along.
4. **Make the stability gate `and`, not `or`** (D-03), or drop the absolute arm.
5. **Have the filter drop rows instead of substituting them** (D-05), or report the substituted
   fraction on the image.
6. **Reconcile the runbook and re-run it end to end** (X-01). A stale gate is worse than no gate.
7. **Reframe Chapter 3's AIoT paragraph and add the anisotropy limitation** (X-02). Both are
   stronger stated openly with citations than left for a panel to find.

---

## Sources

- [Preliminary Evaluation of Electrical Resistance Tomography for Imaging Palm Trunks](https://auf.isa-arbor.com/content/42/2/111)
  — Arboriculture & Urban Forestry. The closest published analogue: 12 nails, DC 12-50 V
  alternating polarity, 3-10 mA, and the healthy-baseline caveat.
- [PiCUS TreeTronic electrical resistance tomograph](https://www.iml-electronic.com/downloads/picus_treetronic_en.pdf)
  — vendor documentation; drive voltages up to 100 V, 12-electrode ring.
- [Noninvasive Analysis of Tree Stems by ERT: Temperature, Water Status, and Electrode Installation](https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2019.01455/full)
  — Frontiers in Plant Science; confounders that dominate tree ERT readings.
- [ERT numerical modeling for decay characteristic analysis in ancient tree stems](https://academic.oup.com/jge/article/23/2/630/8414068)
  — J. Geophysics & Engineering; isotropic models cause boundary blurring, anisotropy-aware
  algorithms are not yet practically available.
- [Electric resistance tomography and stress wave tomography for decay detection in trees](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6407501/)
  — comparison study; ERT outperforms stress-wave in early decay.
- [Shape corrections for 3D EIT](https://iopscience.iop.org/article/10.1088/1742-6596/224/1/012049)
  and [Numerical modelling errors in EIT](https://pubmed.ncbi.nlm.nih.gov/17664647/)
  — circular-boundary assumption severely degrades reconstruction; difference imaging is the
  standard mitigation.
- [Analysis of Improved Howland Current Pump Configurations](https://www.ti.com/lit/pdf/sboa437)
  and [AN-1515 A Comprehensive Study of the Howland Current Pump](https://www.ti.com/lit/pdf/snoa474)
  — TI; output impedance degrades as `R / mismatch`, 0.1 percent parts may still be insufficient.
- [ADS111x datasheet](https://www.ti.com/lit/ds/symlink/ads1115.pdf) — TI; noise rises steeply
  with data rate, 860 SPS is the noisiest setting available.
- [CD74HC4067 / CD74HCT4067 datasheet](https://www.ti.com/lit/ds/symlink/cd74hc4067.pdf) — TI;
  analog signal range is bounded by the switch supply rails.
