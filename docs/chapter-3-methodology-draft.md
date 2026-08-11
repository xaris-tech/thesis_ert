# Chapter 3

# Methodology

> Working title: Development of an AIoT-Enabled Electrical Resistivity Tomography (ERT)-Based Tree Health Classification System for Coconut Palm (*Cocos nucifera*)

This is the single methodology document for the project. It absorbs the former
`thesis-methodology-outline.md` and `thesis-method-basis.md`. Where it states a
decision, the authority is the corresponding ADR in `docs/adr/`, and the
vocabulary is defined in `CONTEXT.md`.

## 3.1 Research Design

This study follows a developmental and experimental research design. It focuses on the design, construction, calibration, and preliminary validation of an AIoT-enabled Electrical Resistivity Tomography (ERT)-based prototype for coconut palm (*Cocos nucifera*) health-category assessment.

The study develops a low-cost direct-current ERT prototype capable of switching 12 electrodes, injecting current, measuring voltage and current, storing field data locally, and producing conductivity variation patterns. The system is evaluated through a staged validation ladder before testing on standing living coconut trees.

Evidence is gathered at two levels, and they are not interchangeable:

| Level | Ground truth | What it can support |
|---|---|---|
| Cut-trunk pilot | Operator-created: defect position, size and stage are known facts | Quantitative claims about detection and localization; classifier training and evaluation |
| Standing-tree field study | Philippine Coconut Authority expert category labels only | Descriptive comparison of conductivity variation patterns between categories |

The prototype does not diagnose a named coconut disease. Expert evaluation provides the health-category label; the ERT prototype provides conductivity variation patterns and classifier-ready features.

The field study is open-ended in size, limited by how many expert-evaluated trees the Philippine Coconut Authority can provide, rather than fixed at a set number.

## 3.2 System Development Method

The prototype consists of hardware acquisition, local edge processing, and offline-first AIoT data handling.

| Component | Function |
|---|---|
| ESP32-S3 | Controls I2C devices, electrode switching, and serial data output. |
| MCP4725 DAC | Provides the command signal for current injection. |
| OPA2134PA Improved Howland Current Pump | Generates the controlled current used for ERT measurement. |
| ADS1115 ADC | Measures electrode voltage and current-shunt voltage. |
| CD74HC4067 multiplexers (x4) | Switch current source, current return, voltage-positive, and voltage-negative electrode paths. |
| 12 stainless steel screw electrodes | Provide electrical contact around the coconut trunk or test sample. |
| 100 ohm current shunt | Converts return current into measurable voltage. |
| Raspberry Pi | Stores field data locally, runs the acquisition workflow, and syncs outputs to cloud storage. |

Measurement is **tetrapolar**: current is injected through one electrode pair while voltage is measured across a different pair. The voltage electrodes carry essentially no current, so their contact resistance largely drops out of the reading, and the injected current is measured directly across the shunt rather than assumed. This is what makes the measurement robust to the variable contact impedance of screws in wood.

The ESP32-S3 sends structured scan records to the Raspberry Pi through USB serial, chosen because the firmware already emits structured records and the Python workflow already reads serial data. The Raspberry Pi serves as the field computer, performing the role currently handled by the laptop-based workflow: receiving scan records, saving raw logs, generating reconstruction outputs, preparing feature files, and uploading to Google Drive when connectivity is available.

## 3.3 AIoT Data Handling

The prototype uses an offline-first approach. Field acquisition must continue without internet access. Scan records and outputs are stored locally on the Raspberry Pi and uploaded when connectivity becomes available.

For each scan, the following are stored locally and synced to Google Drive:

| File type | Purpose |
|---|---|
| Raw CSV log | Preserves the original scan records from the ESP32-S3. |
| Reconstruction image | Provides visual output from the reconstruction process. |
| Averaged reconstruction image | Summarizes repeated scan behavior. |
| Feature summary CSV or JSON | Stores classifier-ready values. |
| Completed field data sheet | Preserves metadata and field observations. |
| Tree/electrode photos | Documents setup, condition, and electrode placement. |

The cloud component supports storage, review, and classifier development. It is not required for live acquisition.

## 3.4 Electrode Arrangement

The electrode layout is a twelve-electrode ring labeled E1 to E12. For standing living trees the ring is placed at 1.3 m above ground level, adapted from the diameter-at-breast-height convention used in forestry measurement, giving a repeatable trunk band rather than an arbitrary scan height.

For each subject, trunk circumference at the scan height is measured and divided by 12 to determine equal arc spacing. E1 is placed facing a fixed visible landmark, and E2 through E12 are labeled clockwise from E1, preserving orientation so reconstruction sectors remain interpretable.

Placement procedure:

1. Measure 1.3 m from the ground and mark the scan band.
2. Measure the trunk circumference at the scan band.
3. Divide the circumference by 12 to calculate electrode spacing.
4. Mark the 12 electrode positions around the trunk.
5. Place E1 facing a fixed visible landmark.
6. Label E2 through E12 clockwise from E1.
7. Insert each screw electrode to an initial depth of about 1 cm.
8. Record the **actual** position of each electrode, not only the intended spacing.
9. Adjust insertion only when needed to obtain stable electrical contact.

**Electrode material.** 304/316 stainless steel screws are used. Iron nails were used in earlier bring-up and are not used for recorded results: iron corrodes in sap within hours and its oxide layer is an unstable conductor, so contact impedance drifts continuously and differently at each of the twelve electrodes. Screws also grip more repeatably than hammered nails, making insertion depth consistent and removal non-destructive. See ADR 0004.

Step 8 matters for the reconstruction model. Placement error is the dominant geometric error term: 1 cm of error on 8 cm spacing is 12 percent, larger than the shape error of treating a fairly round palm as circular.

No drilling, hollowing, or deliberate defect creation is performed on standing living coconut trees.

## 3.5 Current Measurement And Current Range

The prototype uses a 100 ohm current shunt in the current return path:

```cpp
constexpr float SHUNT_OHMS = 100.0f;
```

At this shunt value:

| Current | Shunt voltage |
|---:|---:|
| 100 uA | 10 mV |
| 300 uA | 30 mV |
| 500 uA | 50 mV |

The provisional field current range is 100 to 500 uA, with about 300 uA as the initial target. This is not treated as a final biological or field threshold. Very low readings, especially near the previously observed weak-current level of approximately 14 uA, are treated as unreliable for reconstruction.

**Compliance ceiling.** Every node in the current path must remain inside the 3.3 V multiplexer supply rail, capping drivable load at roughly 10.7 kOhm at 300 uA once the shunt and two mux channels are accounted for. Measured electrode-to-electrode resistance on coconut trunk material is about 1.5 kOhm, where approximately 1.8 mA is available — roughly six times the required headroom. No hardware change is needed. A subject measuring above about 9 kOhm would present as repeated `I_LOW` flags rather than as a wiring fault, and would require raising the analog rail.

**Current level selection.** DAC code 100 produces approximately 335 uA and uses about a sixth of the available current. Because hum, thermal and ADC noise are fixed in absolute terms while signal scales with current, higher current should improve signal-to-noise; but higher current also thickens the electrode polarization layer, which is a drift mechanism. The operating current is therefore selected by sweeping DAC codes 100, 150, 200 and 300 on the saline phantom and recording drift against the 5th-percentile measurement voltage at each, rather than being assumed.

Thesis wording until final calibration data exists:

> The prototype used a 100 ohm current shunt and initially targeted microamp-level current injection in the 100-500 uA range. The final operating current for coconut tree scans was selected after bench and field calibration, based on stable current readings, safe hardware limits, and repeatable reconstruction behavior.

## 3.6 Signal Chain Configuration

Measurement stability depends on configuration choices that are easy to overlook and were corrected during development (ADR 0004).

**ADC resolution.** The voltage channel uses `GAIN_EIGHT` (±512 mV, 15.6 uV per count). An earlier configuration used `GAIN_ONE` (±4.096 V, 125 uV per count) against signals of roughly 13 mV, so a median measurement occupied only 106 of 32,768 available counts and quantisation error alone exceeded the 2 percent stability limit on 9.8 percent of measurements. Because quantisation is a fixed grid rather than random noise, averaging cannot remove it. The current-shunt channel remains at `GAIN_SIXTEEN` because 300 uA across 100 ohm produces only 30 mV.

**Frame duration.** Injection must be configured once per injection pair and held while the voltage-sense multiplexers sweep, rather than being torn down and rebuilt for every measurement. The earlier structure re-established the injection path 216 times per frame, collapsing and re-forming the electrode polarization layer each time, with settle time spent waiting for it to recover. This matters because tuning results showed drift growing with elapsed time: 100 ms settle with 16 samples gave 9.20 percent relative drift, while 200 ms with 16 samples gave 18.60 percent despite every parameter being nominally more conservative. Longer settle bought elapsed time, not stability.

**Mains rejection.** Averaging windows should span a whole number of 60 Hz mains cycles, since a fractional window leaves a residue that varies per measurement and cannot be averaged out. Continuous-mode sampling of 43 samples at 860 SPS gives 50.0 ms, exactly three cycles. Whether mains coupling is a material contributor is established first by comparing baseline drift with the acquisition laptop on battery against mains power.

**Acceptance thresholds.** The baseline stability gate is derived from the measured size of a known phantom target response, requiring session drift to sit a stated factor below it, rather than from an inherited fixed percentage. A gate that is not referenced to real signal size cannot be defended, and may block work unnecessarily.

## 3.7 Calibration And Validation Ladder

The prototype is evaluated through four stages:

1. Dummy-load verification
2. Saline phantom testing
3. Cut-trunk pilot testing
4. Standing-tree field study

Each stage must pass before the next begins. The cut-trunk pilot is where the prototype is verified against known ground truth; the field study begins only after it passes.

## 3.8 Dummy-Load Verification

Dummy-load verification confirms the current source, shunt measurement, DAC control, and safety limits before any conductive medium or trunk material is used.

Initial wiring, bypassing the electrode multiplexers:

```text
HCP current output -> dummy resistor -> 100 ohm shunt -> system ground
```

Shunt voltage is measured with a multimeter and current calculated as:

```text
I = Vshunt / 100 ohm
```

Loads tested: 1 kOhm, 4.7 kOhm, 10 kOhm. DAC codes tested per load: 50, 100, 200, 300, 400. Testing begins at DAC code 100 for safe bring-up, and the sweep stops early if current, voltage, or quality flags approach unsafe conditions.

The dummy-load phase passes when:

1. Known resistor loads produce stable measurable current.
2. ADS1115-reported current approximately matches multimeter-confirmed current.
3. Current increases predictably with DAC code.
4. Mux analog signals and ADS1115 inputs remain within safe range.
5. The selected setting avoids `I_LOW`, `I_HIGH`, `I_REVERSED`, and `V_RANGE`.

After the direct path passes, the same loads are tested through the selected mux source and return paths.

Before trusting any field reconstruction, confirm in order:

1. The physical shunt is 100 ohm.
2. Firmware still uses `SHUNT_OHMS = 100.0f`.
3. DAC code has been mapped to current using dummy loads.
4. Actual trunk contact produces stable current across injection pairs.
5. Scans with very low, unstable, reversed, or out-of-range current are rejected.

## 3.9 Saline Phantom Testing

The saline phantom is a controlled conductive medium for testing full electrode switching, baseline stability, and reconstruction response. A plastic object serves as the primary non-conductive contrast target. It is a known contrast object, not a disease proxy.

Three target positions are tested: near one electrode sector, near the opposite electrode sector, and near the center.

This stage also produces the **reference target response** — the measured change in transfer resistance caused by moving the plastic target between known positions. That value is the signal scale against which the baseline stability gate is set (section 3.6), and it is measured here because the phantom is the only stage that can be repeated without cost.

The saline phantom phase passes when:

1. Control scans with no object movement remain stable.
2. Current remains within the selected acceptable range.
3. The inserted object produces a repeatable conductivity variation sector.
4. Moving the object to another sector moves the reconstruction response in the same general direction.

## 3.10 Cut-Trunk Pilot Testing

The cut-trunk pilot is the stage that verifies the prototype against ground truth the operator created, and it supplies the labelled dataset used for classification (ADR 0002, ADR 0003).

**Defect ladder.** Each cut trunk is scanned at four cumulative defect stages:

| Stage | Condition |
|---|---|
| `s1-intact` | Intact trunk, before any drilling |
| `s2-side-3cm` | 3 cm top-drilled defect near a known electrode sector |
| `s3-side-8cm` | The same defect widened to 8 cm |
| `s4-center-8cm` | An additional 8 cm defect near the trunk centre |

Defects are created from the cut face by drilling or hollowing into the interior while preserving the outer electrode ring. Each defect must extend at least one electrode spacing **below** the electrode band, so that it crosses the measurement plane; a defect that stops above the ring produces a clean scan of nothing.

The 3 cm stage is declared **exploratory in advance**: it is sized near the resolution limit of a twelve-electrode ring, so whether or not it is detected is a finding about detection threshold rather than a pass or fail.

**Cumulative defects and consecutive differencing.** Drilled defects are permanent, so a condition cannot be re-tested once passed. Every stage is therefore scanned in full, and the difference is taken between *consecutive* stages, which isolates the single defect newly added at that step and makes the cumulative nature harmless. Missing one intermediate scan creates an unrecoverable gap.

**Single session, unbroken ring.** All four stages are drilled and scanned within one continuous working session, with the twelve-electrode ring installed once and never removed, moved or re-seated. A cut trunk loses moisture continuously and moisture is the dominant conductor in wood, so a multi-day ladder would place global drying into every stage-to-stage difference, swamping the local defect signal. If an electrode contact degrades mid-ladder the screw is not touched; whether to exclude that electrode is an analysis-time decision, which remains reversible.

**Drive patterns.** Both adjacent and opposite drive patterns are captured at every stage. Adjacent drive has its weakest sensitivity at the trunk centre, where the stage 4 defect sits, and a pattern can only be differenced against the same pattern at the previous stage — so capturing opposite drive only at the later stages would leave it with nothing to subtract from.

**Sector-varied trunk set.** The identical ladder is run on several cut trunks with the drilled sector differing on each, so that correct localization cannot be explained by a fixed directional bias. Every other factor is held constant across the set: electrode count, drive patterns, defect sizes, session structure, and acquisition settings. Trunk circumference is recorded as a secondary covariate.

**Success criterion, pre-registered.** At stages 3 and 4, the strongest reconstruction sector must match the drilled sector in at least 2 of 3 repeat runs. This criterion is fixed before any image is produced.

The pilot also validates absolute reconstruction at no extra cost: both difference reconstruction (which has a genuine before-and-after here) and absolute reconstruction (which does not yet have established credibility) are run on the same scans. Agreement between them earns absolute reconstruction the right to be used on standing trees, where no time baseline exists.

## 3.11 Standing-Tree Field Study

Standing living coconut tree scans are observational. Only the twelve minimally invasive screw electrodes are used at the scan band. No drilling, hollowing, or deliberate defect creation is performed. Artificial defects are confined to the cut-trunk pilot.

Trees are selected by Philippine Coconut Authority expert evaluation into three categories:

| Tree category | Selection basis |
|---|---|
| Healthy | No visible symptoms and no specific suspicion of internal degradation. |
| Asymptomatic | No visible external decay but possible hidden disease, damage, or degradation risk. |
| Diseased | Visible symptoms or indicators consistent with disease or internal degradation. |

More than one tree per category is scanned wherever access allows. With a single tree per category, a category difference cannot be distinguished from an individual tree's quirk, which is the first question a reader will ask.

Field testing is covered by an organized permission document with the Philippine Coconut Authority and tree owners.

Per tree the method uses: 12 screw electrodes, 1.3 m scan height, equal arc spacing with actual positions recorded, landmark-oriented E1, and three runs of each drive pattern.

**Field baseline is a quality control, not an imaging reference** (ADR 0001). Repeated reference scans on a tree establish whether acquisition held stable for that session, admitting or rejecting the session's data. They are never subtracted to produce a tree image, because the tree cannot be scanned before it became diseased: subtracting two same-session scans of an unchanged tree yields drift, not anatomy.

If electrode contact is poor, scanning stops. The screw is adjusted or reinserted at the same sector, the adjustment is documented, and the full run is restarted. Partial measurements from before and after adjustment are never combined.

If a tree cannot produce stable current after reasonable contact adjustment, the session is marked failed or unstable, documented, and not used as positive evidence. Where possible the tree is replaced by a backup tree in the same category, selected through the same expert evaluation process.

## 3.12 Data Recording

**Every scan records what it looked at.** The specimen identifier and defect stage are written into every row of the raw CSV and into its filename. A scan whose specimen and stage can only be inferred from a timestamp is unusable later, and cut-trunk stages cannot be re-scanned to recover the label.

For each standing living tree, recorded per `docs/field-data-sheet-template.md`:

| Data group | Recorded items |
|---|---|
| Tree information | Tree ID, category, location, date, time, PCA expert notes, visible condition notes |
| Optional tree metadata | Estimated age and coconut variety, when known |
| Environmental notes | Recent rain, trunk surface wetness, soil wetness, weather |
| Electrode setup | Scan height, circumference, electrode spacing, actual electrode positions, E1 landmark, insertion notes |
| Scan settings | Pattern, DAC code, settling time, sample count, run number |
| Measurement quality | Current median, current range, quality flags, baseline stability |
| Reconstruction summary | Strongest sector, repeatability, notes |
| Documentation | Tree photos, electrode ring photos, E1 landmark photo |

Environmental notes are recorded because moisture affects conductivity directly.

For each cut-trunk defect stage, a separate written record holds the run identifier, hole dimensions, drill depth, elapsed session time, and any contact problems observed.

## 3.13 Reconstruction Method

Reconstruction is performed with a Jacobian-based Gauss-Newton solver on a finite-element mesh, regularized because the problem is underdetermined: 216 measurements are used to estimate conductivity across roughly 500 mesh elements, so infinitely many internal distributions fit the data and regularization selects the smoothest.

Two reconstruction modes are used, for different stages:

**Difference reconstruction — bench only.** Two scans of the same physical sample are subtracted, cancelling everything that did not change: electrode contact resistance, exact electrode positions, sample shape, and overall moisture. This is used for the saline phantom and for consecutive defect stages of the cut-trunk pilot, where a genuine before-and-after exists.

**Absolute reconstruction — standing trees.** A single scan is reconstructed against a modelled uniform trunk, producing a per-tree conductivity variation pattern with no time baseline. Because there is nothing to subtract, geometry error no longer cancels and the model must represent the real subject: the mesh is scaled to each tree's measured circumference and uses the recorded actual electrode positions rather than a dimensionless unit circle with assumed equal spacing. Absolute reconstruction is used on trees only after it has been shown to agree with difference reconstruction on the cut-trunk pilot, where the answer is known.

A healthy tree is never used as the baseline for an asymptomatic or diseased tree. Differences in trunk size, moisture, electrode contact and geometry would dominate such a comparison.

Reconstruction outputs considered per subject:

1. Individual reconstruction images
2. Averaged reconstruction image
3. Strongest conductivity variation sector
4. Repeatability across runs
5. Relationship to expert-noted area, if available

Localization is reported by electrode sector rather than exact image coordinates — for example near E3-E4, or between E8 and E10. The resulting image is interpreted as a relative conductivity variation pattern, never as an absolute conductivity map.

## 3.14 Feature Extraction And Classification

The classifier is trained and evaluated on cut-trunk data, not on standing trees (ADR 0003). The cut-trunk pilot yields roughly 72 labelled scans across several trunks — four defect stages, two drive patterns, three repeats — each carrying two independent ground-truth labels the operator created: severity stage and drilled sector. The field study yields expert category labels but no operator-controlled ground truth and an unknown sample count.

**Evaluation.** Leave-one-trunk-out cross-validation: all scans from one trunk are held out as the test set and the model trained on the remaining trunks, so reported scores reflect performance on a trunk never seen during training. Any scaling or dimensionality reduction is fitted inside each fold, never before splitting.

**Features.** Each scan is reduced to roughly 10 to 20 physically interpretable summary features rather than its 216 raw transfer resistances, drawn from the raw measurement ring profile, reconstruction output, current quality, and run repeatability:

| Feature group | Example features |
|---|---|
| Raw ERT features | Normalized transfer resistance profile around the ring, sector contrast, spread across the ring |
| Current quality features | Current median, current range, quality flag counts |
| Reconstruction features | Strongest electrode sector, sector intensity |
| Repeatability features | Similarity of strongest sector across runs, baseline stability metrics |
| Metadata features | Expert category label and environmental notes, for later analysis |

**Model.** Logistic regression or a shallow decision tree. With roughly 72 samples, using all 216 raw measurements would give three times more features than samples and would fit noise, and a flexible model on all features would most likely learn trunk identity rather than defect state.

Standing-tree scans are reported descriptively and are not fed to the trained model: a model fitted to drilled holes in cut wood has no established relationship to disease in living tissue. Target categories are limited to healthy, asymptomatic and diseased. The classifier is never used to identify a named disease.

## 3.15 Data Analysis And Results Presentation

Cut-trunk results are reported per defect stage against known ground truth:

| Specimen | Drilled sector | Stage | Pattern | Strongest sector | Sector match | Repeatability | Notes |
|---|---|---|---|---|---|---|---|
| | | | | | Yes / No | of 3 runs | |

Standing-tree results are reported per tree, grouped by expert category:

| Tree ID | Expert category | Current stability | Repeatability across runs | Strongest sector | Pattern summary | Notes |
|---|---|---|---|---|---|---|

Reconstruction images and averaged reconstruction images are used as supporting figures. The analysis addresses two separate questions: whether the prototype localizes known defects in the cut-trunk set, and whether trees within an expert category resemble each other and differ from other categories.

## 3.16 Failure And Inconclusive Conditions

A scan or session is marked failed or inconclusive when any of the following occur:

1. Current is unstable or too low for trustworthy reconstruction.
2. Baseline stability fails against the signal-referenced gate.
3. Reconstructions are not repeatable across runs.
4. Scans cannot be completed because of contact, wiring, power, or acquisition problems.
5. Required frame data are incomplete.
6. Major quality flags appear repeatedly.

Failed or inconclusive scans are documented but never used as positive evidence that the prototype works. An undetected 3 cm exploratory defect is not a failure — it is a resolution-limit finding.

## 3.17 Minimum Thesis Deliverable

The minimum final system deliverable is a working AIoT-ready ERT prototype that:

1. Acquires stable 12-electrode data.
2. Produces repeatable reconstructions that localize known defects in the cut-trunk set.
3. Extracts classifier-ready features and reports an evaluated classification result on ground-truth data.
4. Compares expert-labelled healthy, asymptomatic and diseased coconut trees descriptively.

The minimum deliverable does not require a validated disease diagnostic model.

## 3.18 Ethical And Practical Boundaries

Standing-tree testing is minimally invasive and observational. No drilling, hollowing, or artificial defect creation is performed on living trees.

The study avoids overclaiming. The system does not:

- diagnose coconut disease
- detect a named disease
- replace Philippine Coconut Authority expert evaluation
- produce absolute conductivity maps
- provide a validated AI diagnostic classifier

If all validation stages pass, the safe success claim is:

> The developed AIoT-ready DC ERT prototype successfully acquired repeatable 12-electrode measurements, localized known artificial defects in coconut trunk material against pre-registered criteria, produced conductivity variation patterns from standing living coconut trees, and generated classifier-ready features evaluated on ground-truth defect data for future health-category classification.

## 3.19 Chapter Summary

This chapter presented the methodology for developing and validating the AIoT-enabled ERT-based coconut palm assessment prototype. The method begins with hardware calibration using dummy loads, proceeds to controlled saline phantom testing, then to a cut-trunk pilot in which defects of known position and size provide ground truth for both localization and classifier evaluation, and finally to observational field testing of expert-evaluated standing living coconut trees. Data are stored locally on a Raspberry Pi and synchronized to Google Drive when connectivity is available. The methodology emphasizes repeatable acquisition, pre-registered acceptance criteria, separation of ground-truth evidence from descriptive field evidence, and cautious interpretation without claiming validated disease diagnosis.

## References For Methodological Basis

- Forest Research. (2014). *National Forest Inventory Survey Manual: Section 15, Diameter (DBH) Assessments*. https://cdn.forestresearch.gov.uk/2022/02/15_diameter_dbh_assessments_june_2014.pdf
- Ganthaler et al. *Noninvasive Analysis of Tree Stems by Electrical Resistivity Tomography*. Frontiers in Plant Science. https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2019.01455/full
- Humplik and Cermak. *Electrical impedance tomography for decay diagnostics of Norway spruce*. Silva Fennica. https://www.silvafennica.fi/article/1341
- Tian et al. *Tree Diameter at Breast Height (DBH) Estimation Using an iPad Pro LiDAR Scanner*. Forests. https://www.mdpi.com/1999-4907/15/1/214
- Wu et al. *Estimation of Diameter at Breast Height in Tropical Forests Based on Multi-Parameters*. Sustainability. https://www.mdpi.com/2071-1050/16/6/2275
