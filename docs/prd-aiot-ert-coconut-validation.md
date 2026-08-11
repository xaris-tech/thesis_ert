# PRD: AIoT-Ready ERT Coconut Palm System

This is the single product definition for the project. It absorbs the former
`phase3a-aiot-ert-prototype-prd.md`. Methodology lives in
`docs/chapter-3-methodology-draft.md`, vocabulary in `CONTEXT.md`, and the
reasoning behind contested decisions in `docs/adr/`.

Intended issue label: `ready-for-agent`

## Problem Statement

The project needs a defensible path from the current Phase 3A ERT prototype to a working thesis system for coconut palm health-category assessment, supporting the thesis:

> Development of an AIoT-Enabled Electrical Resistivity Tomography (ERT)-Based Tree Health Classification System for Coconut Palm (*Cocos nucifera*)

The prototype has working pieces: ESP32-S3 firmware, MCP4725-controlled current drive, ADS1115 voltage and current measurement, four-mux 12-electrode switching, Python reconstruction tooling, and logs showing usable current levels. What is missing is a repeatable end-to-end workflow — bench calibration, phantom validation, cut-trunk verification against known ground truth, field scans, local storage, cloud sync, feature extraction, and clear pass/fail evidence — that produces results without overclaiming disease diagnosis, absolute conductivity mapping, or validated AI classification.

The immediate technical risk is not visualisation polish but **measurement repeatability**: grounding, shunt correctness, ADC resolution, frame duration, current magnitude, contact quality, mux-path health, and protocol consistency. Baseline stability failed every tuning preset through July 2026, and the causes turned out to be configuration rather than fundamentals (ADR 0004).

The domain boundary is fixed: the ERT prototype produces conductivity variation patterns and classifier-ready features; Philippine Coconut Authority expert evaluation provides the healthy, asymptomatic and diseased category labels.

## Solution

A staged system, not a single field scan:

1. Calibrate the current path with dummy loads and multimeter confirmation.
2. Validate electrode switching and reconstruction response in a saline phantom, and measure the reference target response that sets the stability gate.
3. Verify against known ground truth using cut-trunk pilots run through a four-stage defect ladder, with the drilled sector varied across trunks.
4. Scan expert-evaluated standing living coconut trees observationally.
5. Store outputs locally on a Raspberry Pi, syncing to Google Drive when connectivity allows.
6. Extract summary features and train and evaluate a classifier on the cut-trunk ground-truth dataset.

Success is not a named disease diagnosis. The safe success claim is in `docs/chapter-3-methodology-draft.md` section 3.18.

## Requirements

### Hardware

- Use the active Phase 3A 12-electrode switched architecture as the product target: ESP32-S3, MCP4725, ADS1115, OPA2134-based improved Howland current pump, four CD74HC4067 multiplexers, a 100 ohm return shunt, and a 12-electrode ring labeled E1 to E12.
- Switch current source, current return, voltage positive and voltage negative independently, so that reconstruction-capable tetrapolar measurements are possible.
- Use 304/316 stainless steel screw electrodes, not iron nails, so that contact impedance does not drift as the electrode corrodes in sap (ADR 0004).
- Preserve the 100 ohm shunt in both hardware and firmware, so that reported current cannot be misread by a factor of ten.
- Keep every analog node inside the multiplexer supply range. Measured trunk resistance of about 1.5 kOhm leaves roughly six times the headroom needed at 300 uA, so the 3.3 V rail is adequate; a subject above about 9 kOhm would require raising it.
- Maintain one signal ground reference, and never tie the op-amp negative rail to logic ground.

### Firmware

- Emit complete frame records carrying drive pattern, DAC code, settling time, sample count, polarity, current pair, voltage pair, voltage, current and quality flag, so the host parser can validate rather than guess.
- Support adjacent and opposite drive patterns selectable at runtime, without reflashing.
- Emit forward and reverse injection records per measurement, so transfer resistance can be normalised against polarity bias.
- Provide explicit safe idle that forces DAC output to zero and disables all multiplexers.
- Provide I2C diagnostics that detect the MCP4725 and ADS1115, so wiring and grounding faults stop work early.
- Flag low, high, reversed and out-of-range measurements, so bad analog behaviour is treated as a hardware problem and not as reconstruction evidence.
- Use `GAIN_EIGHT` for the voltage channel and `GAIN_SIXTEEN` for the shunt channel. Measuring roughly 13 mV signals at `GAIN_ONE` wasted 8x of available resolution and put quantisation error above the stability limit on nearly a tenth of measurements (ADR 0004).
- Configure injection once per injection pair and hold it while the voltage multiplexers sweep, rather than rebuilding the injection path for every measurement. Frame duration is a drift driver, and the old structure re-triggered electrode polarization 216 times per frame (ADR 0004).
- Average over a whole number of mains cycles, so 60 Hz pickup cancels rather than leaving a per-measurement residue.

### Acquisition software

- Run a complete session from one command or one UI action: open the port, configure the board, capture warmup frames, collect baseline frames, then run comparison or control captures.
- Check baseline stability before reconstruction, against a gate derived from the measured phantom target response rather than an inherited fixed percentage.
- Provide control-mode drift analysis without moving the target, so contact drift is distinguishable from a real anomaly response.
- Compute paired transfer resistance from forward and reverse records.
- Highlight the most unstable electrodes and measurement pairs, so debugging targets the weakest part of the ring.
- Report per-frame current summaries during capture, so unusably low current is noticed while scanning rather than afterwards.
- Never mask a measurement for having changed a lot. Noisy-pair exclusion measured while nothing is changing is legitimate; excluding large deltas deletes exactly the defect signal being looked for. Large deltas are counted and reported.
- Save raw CSV logs, per-frame reconstruction images, averaged reconstruction images, and control stability reports for every run, so each session leaves an auditable trail.
- Keep protocol parsing, frame validation, transfer-resistance normalisation, baseline stability assessment, control drift analysis, reconstruction orchestration and raw log writing as separate modules with narrow interfaces.
- Preserve the split between active Phase 3A protocol handling and legacy Phase 2 `SCAN:`-style handling, so assumptions cannot mix.
- Keep the legacy Phase 2 acquisition and export-analysis tools as support utilities. They remain useful for stability summaries and dataset preparation, and must not be presented as proof of tomography completeness.

### Data recording and labelling

- Record specimen identifier and defect stage in every raw CSV row and in every log filename. A scan whose subject can only be inferred from a timestamp is unusable, and cut-trunk stages cannot be re-scanned to recover the label. Logging must refuse to run unlabelled.
- Record the actual measured position of each electrode, not only the intended equal spacing, because placement error dominates the geometric error budget for absolute reconstruction.
- Record trunk circumference, scan height, E1 landmark, insertion notes, current statistics, quality flags, baseline stability, strongest sector and photos per subject.
- Record environmental notes — recent rain, trunk and soil wetness, weather — because moisture directly affects conductivity.
- Keep a per-stage written record for cut-trunk sessions holding run identifier, hole dimensions, drill depth, elapsed session time and any contact problems.

### Validation

- Enforce the ladder in order: dummy load, mux-path check, saline phantom, cut-trunk pilot, standing-tree field study.
- Use direct dummy-load calibration before mux-path calibration, with 1 kOhm, 4.7 kOhm and 10 kOhm loads and DAC codes 50, 100, 200, 300, 400, stopping early on unsafe behaviour.
- Use multimeter-confirmed shunt voltage as the bench reference for current validation.
- Treat 100 to 500 uA with about 300 uA initial as provisional. Select the operating current by sweeping DAC codes on the phantom and recording drift against the weakest measurement voltages.
- Run the cut-trunk defect ladder as four cumulative stages in a single continuous session with the electrode ring installed once and never re-seated, scanning at every stage and differencing consecutive stages (ADR 0002).
- Capture both adjacent and opposite drive patterns at every stage, since a pattern can only be differenced against itself and adjacent drive is weakest at the trunk centre.
- Vary only the drilled sector between trunks, holding all other factors constant.
- Fix the success criterion before any image is produced: strongest reconstruction sector must match the drilled sector in at least 2 of 3 repeat runs at the larger defect stages.
- Keep standing-tree scans observational. Never drill, hollow or create defects in a living tree.
- Restart the full run after any contact adjustment, never combining partial runs from before and after.
- Identify backup trees per category where access allows.

### Reconstruction

- Use difference reconstruction only where the same physical sample can be scanned before and after a change: the phantom, and consecutive cut-trunk defect stages.
- Treat the field baseline as a quality control that admits or rejects a session, never as an imaging reference. Subtracting two same-session scans of an unchanged tree yields drift, not anatomy (ADR 0001).
- Use absolute reconstruction for standing trees, against a mesh scaled to the measured circumference and using recorded actual electrode positions rather than a dimensionless unit circle.
- Validate absolute reconstruction on the cut-trunk pilot, where the answer is known, before trusting it on a tree.
- Never use one tree as the baseline for another.
- Report localization by electrode sector, not exact image coordinates.
- Never present output as an absolute conductivity map.

### Classification

- Train and evaluate the classifier on the cut-trunk dataset, which carries operator-created ground truth for both defect stage and drilled sector (ADR 0003).
- Use leave-one-trunk-out cross-validation, fitting any scaling or dimensionality reduction inside each fold.
- Reduce each scan to roughly 10 to 20 physically interpretable summary features rather than the full 216-value vector.
- Use logistic regression or a shallow tree, not a flexible model that would learn trunk identity from a small sample.
- Report standing-tree results descriptively; do not feed them to the trained model as though the relationship were established.
- Limit target categories to healthy, asymptomatic and diseased. Never identify a named disease.

### AIoT

- Store field outputs locally first. Cloud availability must never be required to acquire data.
- Use USB serial as the first ESP32-S3 to Raspberry Pi acquisition link, since the structured serial protocol already works on both sides.
- Use the Raspberry Pi as the field computer, taking over the role currently held by the laptop workflow.
- Use Google Drive as the initial sync target, uploading raw logs, reconstruction images, averaged images, feature summaries, field sheets and photos when connectivity is available.

## Testing Decisions

- Test external behaviour and contracts at the highest practical seam: serial firmware output, parser behaviour, acquisition and reconstruction CLI behaviour, generated logs, and validation outputs. Do not test private implementation details.
- Test the serial frame parser with valid adjacent and opposite headers, malformed records, missing forward or reverse pairs, bad quality flags, and mismatched frame terminators.
- Test measurement normalisation with known synthetic forward and reverse records, confirming transfer-resistance values and vector ordering.
- Test baseline-stability and control-drift logic with stable, unstable and edge-case datasets so threshold enforcement stays intentional and reviewable.
- Test that captures actually reach disk, labelled with specimen and stage, and that every frame is written. Logging was silently absent from the UI acquisition path for its whole existence.
- Test that large-delta measurements pass through to reconstruction rather than being masked, and that noisy pairs are still excluded.
- Test firmware source-level contracts for pin maps, separate voltage and current ADS1115 reads with their respective gains, forward and reverse records, adjacent and opposite modes, safe mux switching order, quality flags, status constants and I2C diagnostics.
- Test the legacy export analyzer for CSV and NPZ loading, summary statistics and measurement-matrix generation, so Phase 2 artifacts stay trustworthy as support inputs.
- Keep tests hardware-free and deterministic, using the demo acquisition path.
- Keep requirements-based environment setup documented so the suite runs in a local virtual environment.
- Hardware validation cannot be replaced by unit tests. Required bench verification: I2C detection, safe idle, shunt verification, dummy-load current measurement, mux-path continuity, and stable control runs before any reconstruction is trusted.
- Guard against header-only acquisition failures by checking CSV row counts.
- Prior art for expected behaviour: DAC 100 has produced roughly 300-350 uA at `OK` quality. `I_LOW`, `I_HIGH`, `I_REVERSED`, `V_RANGE` and saturated current are electrical failures, not reconstruction evidence.

## Out of Scope

- Named coconut disease diagnosis, or confirmed decay detection in standing living trees.
- Replacing Philippine Coconut Authority expert evaluation.
- Destructive drilling or hollowing of standing living coconut trees.
- Absolute conductivity mapping, or anatomically confirmed internal maps.
- Claiming validated diagnostic classifier performance from the field dataset.
- Treating a single reconstruction image as proof of performance.
- Skipping dummy-load, phantom or cut-trunk validation and moving directly to tree claims.
- Cloud-required live acquisition.
- Custom IoT dashboard development unless requested later.
- Image-only deep learning classifier training.
- Replacing the entire analog stack with a high-end impedance platform in this phase.
- Production-grade waterproof enclosure, PCB design, or deployment hardening.
- Dropping the legacy Phase 2 tools; they are not the final product but remain useful.
- Clinical, arboricultural or commercial diagnostic claims.

## Further Notes

- Success is judged by whether the system repeatedly acquires stable frames, passes control-mode drift checks, and produces an averaged reconstruction that moves sensibly when a known target moves or a known defect is drilled.
- `docs/drift-tuning-presets.md` records tuning attempts that all predate the ADR 0004 changes. Its results are historical and not comparable to future runs; the presets need re-deriving once frame time drops.
- The `ready-for-agent` label should be applied when this PRD is moved into GitHub Issues. Issue creation could not be performed from this environment because the `gh` CLI was unavailable.
- The safest next implementation step is the current setup validation runbook on live hardware: USB serial detection, firmware `?` and `i` diagnostics, safe idle, direct dummy-load checks, mux-path checks, a single adjacent frame, then a short Python control capture.
