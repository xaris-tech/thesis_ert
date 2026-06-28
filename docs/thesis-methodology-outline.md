# Thesis Methodology Outline

Working title:

> Development of an AIoT-Enabled Electrical Resistivity Tomography (ERT)-Based Tree Health Classification System for Coconut Palm (Cocos nucifera)

## 1. Research Design

This study develops and validates a proof-of-concept AIoT-ready DC Electrical Resistivity Tomography prototype for coconut palm health-category assessment. The prototype is evaluated through a staged validation ladder before final testing on standing living coconut trees.

The study does not claim named disease diagnosis. The ERT prototype produces conductivity variation patterns, while the Philippine Coconut Authority expert evaluation provides the health category labels: healthy, asymptomatic, and diseased.

## 2. Prototype System

The hardware system uses:

- ESP32-S3 controller
- MCP4725 DAC
- ADS1115 ADC
- OPA2134PA Improved Howland Current Pump
- four CD74HC4067 multiplexers
- 12 nail electrodes
- 100 ohm current shunt
- Raspberry Pi field computer

The ESP32-S3 controls current injection, electrode switching, voltage measurement, and current-shunt measurement. The Raspberry Pi receives structured serial records over USB, stores field data locally, performs reconstruction or post-processing, and synchronizes outputs to Google Drive when internet connectivity is available.

## 3. Electrode Layout

The final living-tree scan uses a twelve-electrode ring. Twelve iron nail electrodes are placed around the coconut trunk and labeled E1 through E12.

For standing living trees, the electrode ring is placed at 1.3 m above ground level. This follows the diameter-at-breast-height reference commonly used in forestry measurement and provides a repeatable trunk band across trees.

For each tree:

- measure trunk circumference at 1.3 m
- divide circumference by 12
- place electrodes using equal arc spacing
- place E1 facing a fixed visible landmark
- label E2 through E12 clockwise from E1
- start nail insertion at about 1 cm and adjust only for stable contact

No drilling or hollowing is performed on standing living coconut trees.

## 4. Current Calibration

The prototype uses a 100 ohm current shunt. The provisional current range is 100-500 uA, with about 300 uA as the initial target. The final field current range must be selected after calibration.

Calibration begins with direct dummy-load testing:

```text
HCP current output -> dummy resistor -> 100 ohm shunt -> system ground
```

Test resistor loads:

- 1 kOhm
- 4.7 kOhm
- 10 kOhm

Test DAC codes:

- 50
- 100
- 200
- 300
- 400

For each test, compare the ADS1115-reported current against the multimeter-confirmed shunt voltage. Stop early if current or voltage approaches unsafe hardware limits or quality flags appear.

## 5. Validation Ladder

The prototype is validated through four stages:

1. Dummy-load verification
2. Saline phantom testing
3. Cut-trunk pilot testing
4. Final three-tree comparison

The final living-tree comparison should not begin until the earlier stages pass.

## 6. Dummy-Load Verification

The dummy-load phase passes when:

- known resistor loads produce stable current
- measured current approximately matches multimeter verification
- current changes predictably with DAC code
- mux and ADC voltages remain within safe range
- selected settings avoid `I_LOW`, `I_HIGH`, `I_REVERSED`, and `V_RANGE`

After the direct dummy-load path works, the same loads should be tested through the selected mux source and return paths.

## 7. Saline Phantom Testing

The saline phantom is used as a controlled conductive medium before tree testing. A plastic object is used as the primary non-conductive contrast target.

Test three target positions:

- near one electrode sector
- near the opposite electrode sector
- near the center

The saline phantom phase passes when control scans are stable, current remains acceptable, and the reconstruction response moves in the same general direction as the known object position.

## 8. Cut-Trunk Pilot Testing

The cut-trunk pilot uses a cut coconut trunk section to test the electrode method on coconut trunk material before final living-tree scans.

The pilot sequence is:

1. Scan the intact cut trunk.
2. Create a top-drilled or hollowed side-sector defect and scan again.
3. Create a top-drilled or hollowed center defect and scan again, if the trunk remains suitable.

The artificial defects are known contrast targets, not natural disease. Record defect sector, approximate size, depth, and photos before scanning.

The cut-trunk pilot passes when electrode contact is stable, three adjacent-drive runs complete, and repeatable reconstruction patterns appear near the known artificial defect sector when applicable.

## 9. Final Living-Tree Field Test

The final field test compares three standing living coconut trees:

- healthy tree
- asymptomatic tree
- diseased tree

Tree category labels are provided through Philippine Coconut Authority expert evaluation. A backup candidate should be identified for each category if access allows.

Each final tree uses:

- 12 nail electrodes
- 1.3 m scan height
- equal arc spacing
- landmark-oriented E1
- three adjacent-drive scan runs
- optional opposite-drive supplemental scan if stable

If an electrode contact is bad, stop, adjust or reinsert the nail at the same sector, document the adjustment, and restart the full run.

## 10. Data Recording

For each living tree, record:

- Tree ID
- expert category
- location
- date and time
- trunk circumference
- electrode spacing
- E1 landmark
- visible condition notes
- PCA expert notes
- scan settings
- current statistics
- baseline stability
- strongest reconstruction sector
- photos

Optional metadata:

- estimated age
- coconut variety
- recent rain
- trunk surface wetness
- soil wetness
- weather

Use the field data sheet template in `docs/field-data-sheet-template.md`.

## 11. Reconstruction And Localization

The system performs difference reconstruction using each tree's own baseline. A healthy tree is not used as the baseline for a diseased tree.

Localization is reported by electrode sector rather than exact image coordinates. Example: near E3-E4 or between E8 and E10.

For each tree, compare:

- averaged reconstruction image
- strongest conductivity variation sector
- repeatability across three runs
- relationship to expert-noted area, if available

## 12. AIoT And Classifier-Ready Features

The system is AIoT-ready through offline-first data handling:

- ESP32-S3 acquires scan records
- Raspberry Pi stores logs and outputs locally
- Google Drive sync happens when internet is available
- feature files are prepared for future classifier development

The classifier is a prototype or future-facing component. The thesis defines classifier-ready inputs but does not claim validated AI classifier performance from the three-tree dataset.

Classifier-ready features may include:

- normalized raw ERT measurements
- strongest electrode sector
- sector intensity
- current stability metrics
- reconstruction repeatability metrics

## 13. Google Drive Sync Outputs

For each scan, sync:

- raw CSV log
- reconstruction image
- averaged reconstruction image
- feature summary CSV or JSON
- completed field data sheet
- photos of the tree and electrode setup

## 14. Results Presentation

Report the final living-tree comparison with one row per category:

| Tree category | Expert label | Current stability | Repeatability across 3 runs | Strongest sector | Reconstruction pattern summary | Notes |
|---|---|---|---|---|---|---|
| Healthy | | | | | | |
| Asymptomatic | | | | | | |
| Diseased | | | | | | |

Use reconstruction images and averaged reconstruction images as supporting figures.

## 15. Failure Conditions

Treat scans as failed or inconclusive when:

- current is unstable or too low
- baseline stability fails
- reconstructions are not repeatable across three runs
- living-tree scans cannot be completed
- required frame data are incomplete
- major quality flags appear

Failed or inconclusive scans should be documented but not used as positive evidence.

## 16. Safe Success Claim

If all validation stages pass, the thesis may claim:

> The developed AIoT-ready DC ERT prototype successfully acquired repeatable 12-electrode measurements from coconut palm samples and standing living coconut trees, produced difference reconstructions showing category-associated conductivity variation patterns, and generated classifier-ready features for future health-category classification.

Do not claim that the system diagnoses coconut disease, detects named disease, replaces PCA expert evaluation, produces absolute conductivity maps, or has a validated AI classifier.
