# PRD: AIoT-Ready ERT Coconut Palm Validation System

Intended issue label: `ready-for-agent`

## Problem Statement

The project needs a defensible path from the current Phase 3A ERT prototype to a working thesis system for coconut palm health-category assessment. The user needs the prototype to work on actual standing living coconut trees, but the system must not overclaim disease diagnosis, absolute conductivity mapping, or validated AI classification from a very small field dataset.

The current prototype has promising pieces: ESP32-S3 firmware, MCP4725-controlled current drive, ADS1115 voltage/current measurement, four-mux 12-electrode switching, Python reconstruction tooling, existing logs showing useful current levels, and a thesis methodology. What is missing is a productized validation workflow that turns those pieces into a repeatable end-to-end process: bench calibration, saline phantom validation, cut-trunk pilot testing, living-tree scans, local Raspberry Pi storage, Google Drive sync, feature extraction, and clear pass/fail evidence.

The user needs the system to support a thesis titled:

> Development of an AIoT-Enabled Electrical Resistivity Tomography (ERT)-Based Tree Health Classification System for Coconut Palm (Cocos nucifera)

The work must preserve the agreed domain boundary: the ERT prototype produces conductivity variation patterns and classifier-ready features, while Philippine Coconut Authority expert evaluation provides the healthy, asymptomatic, and diseased category labels.

## Solution

Build and validate an AIoT-ready Phase 3A ERT workflow that can acquire stable 12-electrode measurements, produce repeatable difference reconstructions, extract classifier-ready features, and organize field outputs for later health-category classification work.

The solution is a staged system, not a single field scan:

1. Calibrate the current path using dummy-load verification with multimeter confirmation.
2. Validate electrode switching and reconstruction response in a saline phantom with a plastic phantom target.
3. Validate coconut trunk material behavior using a cut-trunk pilot with top-drilled side-sector and center defects.
4. Perform observational living-tree scans on expert-evaluated healthy, asymptomatic, and diseased coconut trees.
5. Store field outputs locally on a Raspberry Pi and synchronize them to Google Drive when internet is available.
6. Extract combined ERT feature sets from raw measurements and reconstruction summaries for a future prototype classifier component.

The success of the thesis system is not a named disease diagnosis. The safe success claim is that the AIoT-ready DC ERT prototype acquired repeatable 12-electrode measurements from coconut palm samples and standing living coconut trees, produced difference reconstructions showing category-associated conductivity variation patterns, and generated classifier-ready features for future health-category classification.

## User Stories

1. As a thesis researcher, I want a staged validation ladder, so that I can prove the prototype works before scanning standing living coconut trees.
2. As a thesis researcher, I want dummy-load verification with known resistors, so that I can confirm current output before using biological samples.
3. As a thesis researcher, I want multimeter-confirmed shunt current checks, so that I can verify the firmware-reported current is credible.
4. As a thesis researcher, I want the firmware and documentation to agree on the 100 ohm current shunt, so that current readings are not misinterpreted by 10x.
5. As a thesis researcher, I want an I2C diagnostic command on the firmware, so that I can confirm the MCP4725 and ADS1115 are detected before scanning.
6. As a thesis researcher, I want a safe idle command, so that I can force the DAC output to zero and disable muxes before rewiring.
7. As a thesis researcher, I want a direct dummy-load path, so that I can test the current source without mux complexity.
8. As a thesis researcher, I want a mux path check after direct dummy-load validation, so that I can isolate mux or channel failures.
9. As a thesis researcher, I want a provisional 100-500 uA current range with about 300 uA as the initial target, so that field testing starts from a realistic operating point.
10. As a thesis researcher, I want current thresholds to be finalized from actual dummy-load and tree readings, so that the method reflects real hardware behavior.
11. As a thesis researcher, I want the system to reject or flag unstable current, so that bad measurements do not become misleading reconstruction images.
12. As a thesis researcher, I want saline phantom testing, so that I can validate response movement in a controlled conductive medium.
13. As a thesis researcher, I want to use a plastic phantom target, so that I can create a known non-conductive contrast without implying disease simulation.
14. As a thesis researcher, I want three phantom target positions, so that I can test side-sector, opposite-sector, and center responses.
15. As a thesis researcher, I want a cut-trunk pilot, so that I can test coconut trunk material before standing living trees.
16. As a thesis researcher, I want a cut-trunk before-after scan sequence, so that the same trunk can serve as its own reference.
17. As a thesis researcher, I want a top-drilled side-sector defect in the cut trunk, so that I can test coarse electrode-sector localization.
18. As a thesis researcher, I want a top-drilled center defect in the cut trunk, so that I can test central internal variation response.
19. As a thesis researcher, I want artificial defects to be described as known contrast targets, so that the thesis does not confuse them with natural disease.
20. As a thesis researcher, I want final living-tree scans to be observational only, so that standing living coconut trees are not drilled or hollowed.
21. As a thesis researcher, I want to use only minimally invasive nail electrodes on living trees, so that field testing stays within the agreed permission boundary.
22. As a thesis researcher, I want a 12-electrode ring around each tree, so that the final field method matches the Phase 3A hardware.
23. As a thesis researcher, I want the electrode ring at 1.3 m above ground, so that scans use a repeatable forestry-based trunk band.
24. As a thesis researcher, I want equal arc spacing from circumference divided by 12, so that electrode placement adapts to different trunk sizes.
25. As a thesis researcher, I want E1 placed toward a fixed visible landmark, so that reconstruction sectors have a recorded orientation.
26. As a thesis researcher, I want nail insertion to start around 1 cm and adjust only for stable contact, so that electrode placement is repeatable without overclaiming a biological depth.
27. As a thesis researcher, I want contact adjustments to restart the full run, so that partial runs before and after electrode changes are not mixed.
28. As a thesis researcher, I want one backup tree per category if possible, so that unstable contact on one tree does not collapse the whole field study.
29. As a thesis researcher, I want PCA expert evaluation to assign healthy, asymptomatic, and diseased labels, so that category labels do not come from the ERT image alone.
30. As a thesis researcher, I want the device not to claim named disease detection, so that the thesis remains scientifically defensible.
31. As a thesis researcher, I want each tree reconstructed against its own baseline, so that cross-tree differences in size, moisture, and contact do not dominate the result.
32. As a thesis researcher, I want localization reported by electrode sector, so that the output matches the practical resolution of the 12-electrode prototype.
33. As a thesis researcher, I want three adjacent-drive runs per tree, so that repeatability is assessed instead of relying on a single image.
34. As a thesis researcher, I want adjacent drive as the primary pattern, so that the thesis depends on the most stable supported acquisition path.
35. As a thesis researcher, I want opposite drive only as supplemental data, so that optional exploratory scans do not endanger the success condition.
36. As a thesis researcher, I want baseline stability checks, so that reconstructions are blocked when the reference condition is unstable.
37. As a thesis researcher, I want raw CSV logs, so that field measurements can be reviewed and reprocessed later.
38. As a thesis researcher, I want reconstruction images and averaged reconstruction images, so that results can be interpreted visually and compared across runs.
39. As a thesis researcher, I want feature summary files, so that the system prepares data for future classifier development.
40. As a thesis researcher, I want completed field data sheets, so that scan metadata and expert observations are preserved.
41. As a thesis researcher, I want photos of the tree and electrode setup, so that field placement and orientation can be audited.
42. As a thesis researcher, I want optional environmental notes, so that rain, trunk wetness, soil wetness, and weather can explain unusual conductivity behavior.
43. As a thesis researcher, I want Raspberry Pi local storage, so that field acquisition does not depend on internet connectivity.
44. As a thesis researcher, I want USB serial from ESP32-S3 to Raspberry Pi, so that the acquisition link uses the already working structured serial protocol.
45. As a thesis researcher, I want Google Drive sync after local capture, so that field outputs are backed up and shareable when internet becomes available.
46. As a thesis researcher, I want the classifier treated as a prototype component, so that small-sample field results are not presented as validated AI performance.
47. As a thesis researcher, I want combined ERT features from raw values and reconstruction summaries, so that future classification has more useful inputs than images alone.
48. As a thesis adviser, I want clear out-of-scope claims, so that the thesis does not imply diagnostic reliability beyond the evidence.
49. As a PCA expert, I want the system to preserve expert labels separately from ERT outputs, so that expert evaluation is not replaced by the prototype.
50. As a future agent, I want a current setup validation runbook, so that hardware debugging starts at port/I2C/current checks before reconstruction.
51. As a future agent, I want tests around firmware diagnostic constants and serial records, so that firmware documentation and parser assumptions do not drift.
52. As a future agent, I want dependency setup documented, so that Python tests and reconstruction tools can run reproducibly.
53. As a future agent, I want failure conditions defined, so that unstable scans are documented as inconclusive rather than forced into positive evidence.
54. As a future agent, I want the final results table shape defined, so that Chapter 4 can compare categories consistently.
55. As a future agent, I want issue-ready implementation boundaries, so that validation work can be split into independently testable tasks.

## Implementation Decisions

- Use the current Phase 3A unified 12-electrode system as the active prototype target.
- Preserve the 100 ohm current shunt as the physical and firmware current-measurement basis.
- Add or preserve firmware diagnostics that expose the shunt constant and scan the I2C bus for the MCP4725 and ADS1115.
- Keep the serial protocol as the primary ESP32-S3 to host interface.
- Use USB serial as the first ESP32-S3 to Raspberry Pi acquisition link.
- Use the Raspberry Pi as the field computer for local acquisition, storage, reconstruction/post-processing, and later cloud synchronization.
- Use Google Drive as the initial cloud synchronization target.
- Use local-first storage; cloud availability must not be required to acquire field data.
- Keep adjacent-drive scanning as the required primary field pattern.
- Treat opposite-drive scanning as optional supplemental data only when measurements are stable.
- Use a staged validation ladder: dummy-load verification, saline phantom testing, cut-trunk pilot testing, and final three-tree comparison.
- Use direct dummy-load calibration before mux-path dummy-load calibration.
- Use 1 kOhm, 4.7 kOhm, and 10 kOhm dummy loads for current-source calibration.
- Use DAC codes 50, 100, 200, 300, and 400 during dummy-load calibration, stopping early if unsafe behavior appears.
- Use multimeter-confirmed shunt voltage as the bench reference for current validation.
- Treat 100-500 uA, with about 300 uA as an initial target, as provisional until real dummy-load and tree values are measured.
- Treat very low current, saturated current, reversed current, or voltage range flags as acquisition failures, not reconstruction evidence.
- Use a saline phantom with a plastic phantom target as the first controlled reconstruction-response medium.
- Test at least three phantom target positions: side sector, opposite side sector, and center.
- Use a cut-trunk pilot before final living-tree scans.
- Use top-drilled or hollowed artificial defects only in the cut-trunk pilot.
- Test both side-sector and center artificial defects when the cut trunk allows it.
- Keep final living-tree scans observational and minimally invasive.
- Do not drill, hollow, or deliberately create defects in standing living coconut trees.
- Use 12 iron nail electrodes for the prototype field method.
- Place the final living-tree electrode ring at 1.3 m above ground level.
- Determine electrode spacing from trunk circumference divided by 12.
- Orient E1 toward a fixed visible landmark and label E2 through E12 clockwise.
- Start nail insertion around 1 cm and adjust only for stable electrical contact.
- Restart the full scan run after any contact adjustment.
- Identify backup category trees when PCA and tree-owner access allows it.
- Use PCA expert evaluation as the source of healthy, asymptomatic, and diseased category labels.
- Use tree-specific baselines for difference reconstruction.
- Report localization by electrode sector instead of exact image coordinates.
- Generate raw logs, reconstruction images, averaged reconstruction images, feature summaries, field sheets, and setup photos for each scan.
- Use a combined ERT feature set for the future classifier: normalized raw measurements plus reconstruction-derived summary features.
- Treat the classifier as a prototype or future-facing component unless a larger independent dataset is collected.
- Avoid claiming named disease diagnosis, absolute conductivity maps, replacement of PCA expert evaluation, or validated AI classification.

## Testing Decisions

- Test external behavior at the highest practical seam: serial firmware output, parser behavior, acquisition/reconstruction CLI behavior, generated logs, and field validation outputs.
- Do not test private implementation details unless firmware source-level checks are the only available automated seam for Arduino code in this repo.
- Preserve and extend existing Python unit tests for scan parsing, protocol mapping, frame logging, baseline stability, reconstruction output naming, and analyzer behavior.
- Preserve firmware source tests that verify pin maps, separate voltage/current ADS1115 reads, forward/reverse records, adjacent/opposite modes, safe mux switching order, quality flags, status constants, and I2C diagnostics.
- Add or preserve requirements-based environment setup so the full Python suite can run in a local virtual environment.
- Use dummy-load verification as the first hardware test seam.
- Use I2C scan output as the first live firmware diagnostic seam.
- Use a single adjacent frame as the first acquisition seam after I2C and current checks.
- Use short control captures as the first Python acquisition seam before full reconstruction.
- Use baseline stability and quality flags as gates before accepting reconstructions.
- Use CSV log row count as a guard against header-only acquisition failures.
- Use existing good Phase 3A logs as prior art for expected current behavior: DAC 100 can produce roughly 300-350 uA with OK quality.
- Use existing bad logs as prior art for stop conditions: I_LOW, I_HIGH, I_REVERSED, V_RANGE, and saturated current are electrical/acquisition failures.
- Validate final field behavior through three adjacent-drive runs per tree rather than one-off images.
- Treat repeatable electrode-sector patterns as stronger evidence than a single reconstruction frame.
- Compare final tree categories using a structured table with expert label, current stability, repeatability, strongest sector, reconstruction summary, and notes.

## Out of Scope

- Named coconut disease diagnosis.
- Confirmed decay detection in standing living trees.
- Replacing Philippine Coconut Authority expert evaluation.
- Destructive drilling or hollowing of standing living coconut trees.
- Absolute conductivity mapping.
- Validated AI classifier performance from only three final trees.
- Cloud-required live acquisition.
- Custom IoT dashboard development unless requested later.
- Image-only deep learning classifier training.
- Production-grade waterproof enclosure, PCB design, or deployment hardening.
- Clinical, arboricultural, or commercial diagnostic claims.

## Further Notes

- The current repository contains newer Phase 3A work alongside older Phase 2 documentation. Future work should prefer the Phase 3A handover, glossary, validation runbook, and methodology documents when working on the thesis system.
- The `ready-for-agent` label should be applied when this PRD is moved into GitHub Issues.
- GitHub issue creation could not be performed from this environment because the `gh` CLI is not installed and no GitHub token is available.
- The safest next implementation step is to run the current setup validation runbook on live hardware: USB serial detection, firmware `?` and `i` diagnostics, safe idle, direct dummy-load checks, mux-path checks, single adjacent frame, and short Python control capture.
