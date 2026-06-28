# Thesis Method Basis

This document records citation-backed and prototype-backed methodology decisions for the coconut tree ERT thesis.

## Current Acceptance Rule

The active Phase 3A unified firmware uses a **100 ohm current shunt**:

```cpp
constexpr float SHUNT_OHMS = 100.0f;
```

At this value:

- 100 uA produces 10 mV across the shunt.
- 300 uA produces 30 mV across the shunt.
- 500 uA produces 50 mV across the shunt.

Use **100-500 uA** as the provisional field current range, with **about 300 uA** as the initial target. This is not yet the final tree threshold. The final acceptable range must be determined from dummy-load calibration and actual coconut tree readings.

Before trusting field reconstructions:

1. Confirm the physical shunt is 100 ohm.
2. Confirm firmware still uses `SHUNT_OHMS = 100.0f`.
3. Map DAC code to current using dummy loads.
4. Test whether actual coconut tree contact produces stable current across injection pairs.
5. Reject scans where current is very low, unstable, reversed, or outside the safe hardware range.

Do not trust reconstructions when median current is near the previously observed weak-current level around 14 uA.

## Thesis Wording

Use this wording until actual tree calibration data exists:

> The prototype used a 100 ohm current shunt and initially targeted microamp-level current injection in the 100-500 uA range. The final operating current for coconut tree scans was selected after bench and field calibration, based on stable current readings, safe hardware limits, and repeatable reconstruction behavior.

## Validation Ladder

Use a staged validation ladder before final field testing:

1. **Dummy load**: verify that DAC settings produce measurable, repeatable current through known resistor loads.
2. **Saline phantom**: verify full electrode switching, baseline stability, and repeatable reconstruction behavior in a controlled conductive medium.
3. **Cut-trunk pilot**: verify that the electrode method, contact quality, and current range work on a cut coconut trunk section before testing standing living coconut trees.
4. **Final three-tree comparison**: scan the expert-classified healthy, asymptomatic, and diseased coconut trees using the finalized field settings.

Do not skip directly to the final three-tree comparison before the dummy-load, saline, and cut-trunk pilot stages pass.

## Dummy-Load Pass Condition

The dummy-load phase passes when:

1. Known resistor loads produce stable, measurable current.
2. ADS1115-reported current approximately matches the multimeter-confirmed shunt voltage or current.
3. Current increases predictably when DAC code increases.
4. No mux analog signal or ADS1115 input exceeds the safe hardware range.
5. The selected DAC setting can repeatedly produce the provisional current range without `I_LOW`, `I_HIGH`, `I_REVERSED`, or `V_RANGE`.

Use at least these known resistor loads:

- 1 kOhm
- 4.7 kOhm
- 10 kOhm

These loads bracket a useful range for checking whether the current source, shunt measurement, and DAC control behave predictably before saline or tree testing.

Use this DAC sweep for each dummy load:

- 50
- 100
- 200
- 300
- 400

Start at DAC code 100 for initial bring-up, then include 50 and higher values during the full sweep. Stop early if current or voltage approaches unsafe limits or any quality flag appears.

Use the simple direct wiring first:

```text
HCP current output -> dummy resistor -> 100 ohm shunt -> system ground
```

Measure the voltage across the 100 ohm shunt with a multimeter. Convert shunt voltage to current using:

```text
I = Vshunt / 100 ohm
```

After the direct dummy-load path behaves correctly, test the same load values through the selected mux source and return paths.

## Saline Phantom Pass Condition

The saline phantom phase passes when:

1. Control scans with no object movement remain stable.
2. Current remains within the selected acceptable range.
3. A known inserted object produces a repeatable conductivity variation sector.
4. Moving the object to a different sector moves the reconstruction response in the same general direction.

The movable object is a controlled contrast target, not a disease proxy.

Use a plastic object as the primary phantom target. It should act as a non-conductive contrast object relative to saline and should be placed near known electrode sectors so localization can be checked coarsely.

Test three phantom target positions:

1. Near one electrode sector.
2. Near the opposite electrode sector.
3. Near the center of the phantom.

Record the electrode sector for each non-center target position.

## Cut-Trunk Pilot Pass Condition

The cut-trunk pilot phase passes when:

1. All 12 nail electrodes can be placed around the coconut trunk section.
2. Electrode contact is stable enough to complete scans.
3. Current remains within the selected acceptable range for most injection pairs.
4. Three adjacent-drive runs complete without major quality flags.
5. Reconstruction outputs show repeatable electrode-sector patterns across the three runs.
6. If an artificial trunk defect is cut into the sample, the repeatable conductivity variation appears near the known defect sector.

The cut-trunk pilot is a procedure and hardware test. It may include a deliberately cut artificial trunk defect, but that defect must be described as a known artificial contrast target, not as natural disease. The preferred defect method is a top-drilled or hollowed region created from the cut face while preserving the outer electrode ring. It is not part of the final healthy, asymptomatic, and diseased standing-tree comparison.

Test two artificial defect positions if the cut trunk allows it:

1. **Side-sector defect**: a top-drilled/hollowed region near a known electrode sector, used to test coarse localization.
2. **Center defect**: a top-drilled/hollowed region near the center, used to test whether the prototype responds to central internal variation.

Record the defect sector, approximate size, depth, and photos before scanning.

Use this cut-trunk scan sequence:

1. Scan the intact cut trunk before drilling.
2. Drill or hollow the side-sector defect and scan again.
3. Drill or hollow the center defect and scan again, if the trunk remains suitable.

Keep the electrode ring fixed during the sequence when possible so the before-after comparison is not dominated by electrode repositioning.

## Living-Tree Field Boundary

Final standing living coconut tree scans are observational. Use only the 12 minimally invasive nail electrodes at the scan band. Do not drill, hollow, or deliberately create defects in standing living coconut trees.

Artificial defects are allowed only in the cut-trunk pilot stage.

Field testing should be covered by the organized permission document with the Philippine Coconut Authority and coconut tree owners.

For each final living tree, record Tree ID, category, location, date/time, trunk circumference at 1.3 m, calculated electrode spacing, E1 landmark, visible condition notes, PCA expert notes, and photos. Record estimated age and coconut variety when available, but treat them as optional metadata.

Optionally record recent rain, trunk surface wetness, soil wetness, and weather during the test because moisture can affect conductivity.

If an electrode contact is bad during a living-tree scan, stop the scan, gently adjust or reinsert the nail at the same sector, document the adjustment, and restart the full run. Do not combine partial measurements captured before and after electrode adjustment.

If a tree cannot produce stable current after reasonable contact adjustment, mark the scan as failed or unstable and do not use its reconstruction image as evidence. When possible, replace it with a backup category tree selected through the same expert evaluation process.

Before final field testing, identify at least one backup candidate per category if PCA and tree-owner access allows it.

## AI Classification Boundary

The AI/ML classifier is a downstream step that should be used only when complete and stable ERT data are available. The classifier may use raw measurement features, reconstruction-derived features, or both, but it should classify only the expert-defined categories: healthy, asymptomatic, and diseased.

Do not use the classifier to claim named disease diagnosis. Do not train or report classifier results from unstable scans, incomplete frames, or reconstructions that fail the current and repeatability checks.

Use a combined ERT feature set for classification: normalized raw ERT measurements plus reconstruction-derived summary features such as strongest electrode sector, sector intensity, and repeatability metrics. Avoid an image-only classifier unless a much larger dataset becomes available.

Because the final field comparison uses only three primary trees, report the classifier as a prototype or future-facing component. The thesis may define the AIoT data pipeline and candidate classifier inputs, but it should not claim validated classifier performance from the three-tree dataset.

## Minimum Thesis Deliverable

The minimum final system deliverable is a working AIoT-ready ERT prototype that:

1. Acquires stable 12-electrode field data.
2. Produces repeatable difference reconstructions.
3. Extracts classifier-ready raw and reconstruction-derived features.
4. Compares healthy, asymptomatic, and diseased coconut trees using Philippine Coconut Authority expert labels.

The minimum deliverable does not require a validated disease diagnostic model.

## AIoT Data Handling

Use offline-first AIoT storage. Field scan records should be stored locally during acquisition, then uploaded or synchronized to cloud storage when internet connectivity is available.

This means field acquisition must not depend on live internet access. The cloud component supports later storage, review, feature aggregation, or classifier development.

In the final prototype, local field storage should be handled by a Raspberry Pi. The Raspberry Pi performs the role currently handled by the laptop-based Python workflow: receiving ESP32-S3 scan records, saving logs and reconstruction outputs locally, and synchronizing data to the cloud when connectivity is available.

Use USB serial as the first acquisition link between the ESP32-S3 and Raspberry Pi. The ESP32-S3 firmware already emits structured serial records, and the Python workflow already reads serial data, so USB serial should be stabilized before adding wireless or cloud-first acquisition paths.

Use Google Drive as the first cloud synchronization target. The Raspberry Pi should keep field outputs locally first, then upload logs, reconstruction images, feature files, and field metadata to Google Drive when internet connectivity is available.

For each scan, sync these files to Google Drive when available:

- raw CSV log
- reconstruction image
- averaged reconstruction image
- feature summary CSV or JSON
- completed field data sheet
- photos of the tree and electrode setup

## Final Results Table

Report the final living-tree comparison with one row per tree category:

| Tree category | Expert label | Current stability | Repeatability across 3 runs | Strongest sector | Reconstruction pattern summary | Notes |
|---|---|---|---|---|---|---|
| Healthy | | | | | | |
| Asymptomatic | | | | | | |
| Diseased | | | | | | |

Use reconstruction images and averaged reconstruction images as supporting figures for the table.

## Failure Conditions

Treat the test as failed or inconclusive when any of these occur:

1. Current is unstable or too low for trustworthy reconstruction.
2. Baseline stability fails.
3. Reconstructions are not repeatable across the three runs.
4. Living-tree scans cannot be completed because of contact, wiring, power, or acquisition problems.
5. Required frame data are incomplete or contain major quality flags.

Failed or inconclusive scans should be documented but not used as positive evidence for the prototype.

## Safe Success Claim

If all validation stages pass, use this claim:

> The developed AIoT-ready DC ERT prototype successfully acquired repeatable 12-electrode measurements from coconut palm samples and standing living coconut trees, produced difference reconstructions showing category-associated conductivity variation patterns, and generated classifier-ready features for future health-category classification.

Do not claim confirmed disease detection or validated diagnostic classification from the current three-tree field comparison.

Avoid claiming that the system:

- diagnoses coconut disease
- detects a named disease
- replaces Philippine Coconut Authority expert evaluation
- produces absolute conductivity maps
- has a validated AI classifier
