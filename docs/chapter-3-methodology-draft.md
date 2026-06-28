# Chapter 3

# Methodology

## 3.1 Research Design

This study follows a developmental and experimental research design. It focuses on the design, construction, calibration, and preliminary validation of an AIoT-enabled Electrical Resistivity Tomography (ERT)-based prototype for coconut palm (*Cocos nucifera*) health-category assessment.

The study develops a low-cost direct-current ERT prototype capable of switching 12 electrodes, injecting current, measuring voltage and current, storing field data locally, and producing difference reconstructions. The system is evaluated through a staged validation process before final testing on standing living coconut trees.

The final field test compares three expert-evaluated coconut tree categories:

| Category | Description |
|---|---|
| Healthy | A standing living coconut tree assessed by expert evaluation as having no visible symptoms and no specific reason for suspected internal degradation. |
| Asymptomatic | A standing living coconut tree with no visible external decay but identified through expert evaluation as having possible hidden disease, damage, or degradation risk. |
| Diseased | A standing living coconut tree with visible symptoms or expert-observed indicators consistent with disease or internal degradation. |

The prototype does not diagnose a named coconut disease. The Philippine Coconut Authority expert evaluation provides the health-category label, while the ERT prototype provides conductivity variation patterns and classifier-ready features for future health-category classification.

## 3.2 System Development Method

The prototype consists of hardware acquisition, local edge processing, and offline-first AIoT data handling. The system architecture is composed of the following major parts:

| Component | Function |
|---|---|
| ESP32-S3 | Controls I2C devices, electrode switching, and serial data output. |
| MCP4725 DAC | Provides the command signal for current injection. |
| OPA2134PA Improved Howland Current Pump | Generates the controlled current used for ERT measurement. |
| ADS1115 ADC | Measures electrode voltage and current-shunt voltage. |
| CD74HC4067 multiplexers | Switch current source, current return, voltage-positive, and voltage-negative electrode paths. |
| 12 nail electrodes | Provide electrical contact around the coconut trunk or test sample. |
| 100 ohm current shunt | Converts return current into measurable voltage. |
| Raspberry Pi | Stores field data locally, runs the acquisition/reconstruction workflow, and syncs outputs to cloud storage. |

The ESP32-S3 sends structured scan records to the Raspberry Pi through USB serial. USB serial is used as the primary acquisition link because the current firmware already emits structured records and the Python workflow already reads serial data. This minimizes communication complexity during field testing.

The Raspberry Pi serves as the final prototype field computer. It performs the role currently handled by the laptop-based Python workflow: receiving scan records, saving raw logs, generating reconstruction outputs, preparing feature files, and uploading data to Google Drive when internet connectivity is available.

## 3.3 AIoT Data Handling

The prototype uses an offline-first AIoT data handling approach. Field acquisition must continue even without internet access. During testing, scan records and output files are stored locally on the Raspberry Pi. When internet connectivity becomes available, the Raspberry Pi uploads the field outputs to Google Drive.

For each scan, the following files are stored locally and synced to Google Drive:

| File type | Purpose |
|---|---|
| Raw CSV log | Preserves the original scan records from the ESP32-S3. |
| Reconstruction image | Provides visual output from the reconstruction process. |
| Averaged reconstruction image | Summarizes repeated scan behavior. |
| Feature summary CSV or JSON | Stores classifier-ready values for future AI/ML work. |
| Completed field data sheet | Preserves metadata and field observations. |
| Tree/electrode photos | Documents setup, tree condition, and electrode placement. |

This cloud component supports storage, review, and future classifier development. It is not required for live field acquisition.

## 3.4 Electrode Arrangement

The final living-tree test uses a twelve-electrode ring. Twelve iron nail electrodes are placed around the coconut trunk and labeled E1 to E12. The electrodes are placed at 1.3 m above ground level for standing living trees. This scan height is adapted from the diameter-at-breast-height convention used in forestry measurement, giving the study a repeatable trunk band instead of an arbitrary scan height.

For each tree, the trunk circumference at the scan height is measured and divided by 12 to determine the equal arc spacing between electrodes. E1 is placed facing a fixed visible landmark, and E2 through E12 are labeled clockwise from E1. This preserves orientation so that reconstruction sectors can be interpreted after scanning.

The electrode placement procedure is:

1. Measure 1.3 m from the ground and mark the scan band.
2. Measure the trunk circumference at the scan band.
3. Divide the circumference by 12 to calculate electrode spacing.
4. Mark the 12 electrode positions around the trunk.
5. Place E1 facing a fixed visible landmark.
6. Label E2 through E12 clockwise from E1.
7. Insert each nail electrode at an initial depth of about 1 cm.
8. Adjust nail insertion only when needed to obtain stable electrical contact.

Iron nails are used as prototype electrodes. This is reported as a prototype constraint because iron nails may have less consistent contact behavior and lower corrosion resistance than stainless steel electrodes. To reduce variation, the same nail type and size should be used for all trees, visibly rusted nails should be avoided, and measurements should be taken soon after electrode insertion.

No drilling, hollowing, or deliberate defect creation is performed on standing living coconut trees. Final living-tree testing is observational and uses only the minimally invasive nail electrodes.

## 3.5 Current Measurement And Initial Current Range

The prototype uses a 100 ohm current shunt in the current return path. The active Phase 3A firmware calculates current using the firmware constant:

```cpp
constexpr float SHUNT_OHMS = 100.0f;
```

At this shunt value:

| Current | Shunt voltage |
|---:|---:|
| 100 uA | 10 mV |
| 300 uA | 30 mV |
| 500 uA | 50 mV |

The provisional field current range is 100 to 500 uA, with about 300 uA as the initial target. This range is not treated as the final biological or field threshold. The final current setting for coconut tree scanning is selected after dummy-load calibration, saline phantom testing, cut-trunk testing, and actual tree contact checks.

Very low current readings, especially near the previously observed weak-current level of approximately 14 uA, are treated as unreliable for reconstruction.

## 3.6 Calibration And Validation Ladder

The prototype is evaluated using a staged validation ladder:

1. Dummy-load verification
2. Saline phantom testing
3. Cut-trunk pilot testing
4. Final three-tree comparison

The final living-tree comparison is performed only after the earlier validation stages demonstrate stable current, stable acquisition, and repeatable reconstruction behavior.

## 3.7 Dummy-Load Verification

Dummy-load verification is used to confirm the current source, current-shunt measurement, DAC control, and safety limits before testing conductive media or coconut tree material.

The initial dummy-load wiring is:

```text
HCP current output -> dummy resistor -> 100 ohm shunt -> system ground
```

The voltage across the 100 ohm shunt is measured using a multimeter. Current is calculated using:

```text
I = Vshunt / 100 ohm
```

The following dummy resistor loads are tested:

| Load |
|---:|
| 1 kOhm |
| 4.7 kOhm |
| 10 kOhm |

For each load, the following DAC codes are tested:

| DAC code |
|---:|
| 50 |
| 100 |
| 200 |
| 300 |
| 400 |

Testing begins at DAC code 100 for safe bring-up. The sweep is stopped early if current, voltage, or quality flags approach unsafe conditions. The dummy-load phase passes when:

1. Known resistor loads produce stable measurable current.
2. ADS1115-reported current approximately matches multimeter-confirmed current.
3. Current increases predictably with DAC code.
4. Mux analog signals and ADS1115 inputs remain within safe range.
5. The selected setting avoids `I_LOW`, `I_HIGH`, `I_REVERSED`, and `V_RANGE`.

After the direct dummy-load path passes, the same load values are tested through the selected mux source and return paths.

## 3.8 Saline Phantom Testing

The saline phantom is used as a controlled conductive medium for testing full electrode switching, baseline stability, and reconstruction response. A plastic object is used as the primary non-conductive contrast target. The plastic object is not treated as a disease proxy. It is only a known contrast object.

Three target positions are tested:

1. Near one electrode sector
2. Near the opposite electrode sector
3. Near the center of the phantom

The saline phantom phase passes when:

1. Control scans with no object movement remain stable.
2. Current remains within the selected acceptable range.
3. The inserted object produces a repeatable conductivity variation sector.
4. Moving the object to another sector moves the reconstruction response in the same general direction.

The purpose of this phase is to prove controlled response movement before scanning coconut trunk material.

## 3.9 Cut-Trunk Pilot Testing

The cut-trunk pilot uses a cut coconut trunk section to test the electrode method on real coconut trunk material before final testing on standing living trees.

The cut trunk is scanned in a before-after sequence:

1. Scan the intact cut trunk before drilling.
2. Create a top-drilled or hollowed side-sector defect and scan again.
3. Create a top-drilled or hollowed center defect and scan again, if the trunk remains suitable.

The artificial defects are created from the cut face by drilling or hollowing into the interior while preserving the outer electrode ring. Two artificial defect positions are tested when possible:

| Defect type | Purpose |
|---|---|
| Side-sector defect | Tests coarse localization near a known electrode sector. |
| Center defect | Tests response to central internal variation. |

The defect sector, approximate size, depth, and photos are recorded before scanning. These artificial defects are described only as known contrast targets. They are not described as natural disease or confirmed decay.

The cut-trunk pilot phase passes when:

1. All 12 nail electrodes can be placed around the trunk section.
2. Electrode contact is stable enough to complete scans.
3. Current remains within the selected acceptable range for most injection pairs.
4. Three adjacent-drive runs complete without major quality flags.
5. Reconstruction outputs show repeatable electrode-sector patterns.
6. When artificial defects are used, repeatable conductivity variation appears near the known defect sector.

## 3.10 Final Living-Tree Field Test

The final field test compares three standing living coconut trees:

| Tree category | Selection basis |
|---|---|
| Healthy | PCA expert evaluation indicates no visible symptoms and no specific suspicion of internal degradation. |
| Asymptomatic | PCA expert evaluation indicates no visible external decay but possible hidden disease, damage, or degradation risk. |
| Diseased | PCA expert evaluation indicates visible symptoms or indicators consistent with disease or internal degradation. |

Field testing is covered by an organized permission document with the Philippine Coconut Authority and coconut tree owners. Backup trees in each category should be identified when access allows, in case a selected tree cannot produce stable measurements.

For each tree, the method uses:

- 12 nail electrodes
- 1.3 m scan height
- equal arc spacing
- fixed landmark orientation for E1
- three adjacent-drive scan runs
- optional opposite-drive supplemental scan if stable

Adjacent-drive scanning is the primary scan pattern. Opposite-drive scanning may be collected as supplemental exploratory data only when measurements are stable. The success of the thesis does not depend on opposite-drive performance.

If electrode contact is poor, scanning is stopped. The nail is gently adjusted or reinserted at the same sector, the adjustment is documented, and the full run is restarted. Partial measurements collected before and after contact adjustment are not combined.

If a tree cannot produce stable current after reasonable contact adjustment, the scan is marked failed or unstable. Its reconstruction is documented but not used as positive evidence. When possible, the tree is replaced by a backup category tree selected through the same expert evaluation process.

## 3.11 Data Collection Sheet

For each final living tree, the following data are recorded:

| Data group | Recorded items |
|---|---|
| Tree information | Tree ID, category, location, date, time, PCA expert notes, visible condition notes |
| Optional tree metadata | Estimated age and coconut variety, when known |
| Environmental notes | Recent rain, trunk surface wetness, soil wetness, weather |
| Electrode setup | Scan height, circumference, electrode spacing, E1 landmark, insertion notes |
| Scan settings | Pattern, DAC code, settling time, sample count, run number |
| Measurement quality | Current median, current range, quality flags, baseline stability |
| Reconstruction summary | Strongest sector, repeatability, notes |
| Documentation | Tree photos, electrode ring photos, E1 landmark photo |

The field data sheet template is stored in `docs/field-data-sheet-template.md`.

## 3.12 Reconstruction Method

The system performs difference reconstruction. Each tree is reconstructed against its own baseline. A healthy tree is not used as the baseline for the asymptomatic or diseased tree because differences in trunk size, moisture, electrode contact, and geometry would dominate the comparison.

The tree-specific baseline allows the study to examine relative conductivity variation patterns within each tree. The resulting reconstruction image is interpreted as a relative conductivity variation pattern, not as an absolute conductivity map.

For each tree, the following reconstruction outputs are considered:

1. Individual reconstruction images
2. Averaged reconstruction image
3. Strongest conductivity variation sector
4. Repeatability across three runs
5. Relationship to expert-noted area, if available

Localization is reported by electrode sector rather than exact image coordinates. For example, a result may be reported as near E3-E4 or between E8 and E10.

## 3.13 Feature Extraction For AI Classification

The AI/ML classifier is treated as a prototype or future-facing component. The study defines the classifier-ready feature pipeline but does not claim validated classifier performance from the three-tree dataset.

The classifier-ready feature set may include:

| Feature group | Example features |
|---|---|
| Raw ERT features | Normalized voltage/current-derived measurements, transfer resistance values |
| Current quality features | Current median, current range, quality flag counts |
| Reconstruction features | Strongest electrode sector, sector intensity, reconstruction summary values |
| Repeatability features | Similarity of strongest sector across three runs, baseline stability metrics |
| Metadata features | Expert category label and optional environmental notes for later analysis |

The classifier target categories are limited to healthy, asymptomatic, and diseased. The classifier is not used to identify a named disease. Since the final field comparison uses only three main trees, the classifier is not reported as a validated diagnostic model.

## 3.14 Data Analysis And Results Presentation

The final living-tree comparison is reported using one row per expert-defined tree category:

| Tree category | Expert label | Current stability | Repeatability across 3 runs | Strongest sector | Reconstruction pattern summary | Notes |
|---|---|---|---|---|---|---|
| Healthy | | | | | | |
| Asymptomatic | | | | | | |
| Diseased | | | | | | |

Reconstruction images and averaged reconstruction images are used as supporting figures. The analysis focuses on whether each tree category produces stable and repeatable conductivity variation patterns, and whether category-level differences are observable when interpreted with PCA expert evaluation.

## 3.15 Failure And Inconclusive Conditions

The test is marked failed or inconclusive when any of the following occur:

1. Current is unstable or too low for trustworthy reconstruction.
2. Baseline stability fails.
3. Reconstructions are not repeatable across the three runs.
4. Living-tree scans cannot be completed because of contact, wiring, power, or acquisition problems.
5. Required frame data are incomplete.
6. Major quality flags appear repeatedly.

Failed or inconclusive scans are documented, but they are not used as positive evidence that the prototype works.

## 3.16 Ethical And Practical Boundaries

The final living-tree testing is minimally invasive and observational. No drilling, hollowing, or artificial defect creation is performed on standing living coconut trees. Artificial defects are created only in the cut-trunk pilot stage.

The study avoids overclaiming. The system does not:

- diagnose coconut disease
- detect a named disease
- replace Philippine Coconut Authority expert evaluation
- produce absolute conductivity maps
- provide a validated AI classifier

If all validation stages pass, the safe success claim is:

> The developed AIoT-ready DC ERT prototype successfully acquired repeatable 12-electrode measurements from coconut palm samples and standing living coconut trees, produced difference reconstructions showing category-associated conductivity variation patterns, and generated classifier-ready features for future health-category classification.

## 3.17 Chapter Summary

This chapter presented the methodology for developing and validating the AIoT-enabled ERT-based coconut palm assessment prototype. The method begins with hardware calibration using dummy loads, proceeds to controlled saline phantom testing, then cut-trunk pilot testing, and finally field testing on three PCA expert-evaluated standing living coconut trees. The system stores data locally on a Raspberry Pi and synchronizes outputs to Google Drive when internet connectivity is available. The methodology emphasizes repeatable acquisition, controlled validation, cautious interpretation, and classifier-ready feature generation without claiming validated disease diagnosis.

## References For Methodological Basis

- Forest Research. (2014). *National Forest Inventory Survey Manual: Section 15, Diameter (DBH) Assessments*. https://cdn.forestresearch.gov.uk/2022/02/15_diameter_dbh_assessments_june_2014.pdf
- Ganthaler et al. *Noninvasive Analysis of Tree Stems by Electrical Resistivity Tomography*. Frontiers in Plant Science. https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2019.01455/full
- Humplik and Cermak. *Electrical impedance tomography for decay diagnostics of Norway spruce*. Silva Fennica. https://www.silvafennica.fi/article/1341
- Tian et al. *Tree Diameter at Breast Height (DBH) Estimation Using an iPad Pro LiDAR Scanner*. Forests. https://www.mdpi.com/1999-4907/15/1/214
- Wu et al. *Estimation of Diameter at Breast Height in Tropical Forests Based on Multi-Parameters*. Sustainability. https://www.mdpi.com/2071-1050/16/6/2275
