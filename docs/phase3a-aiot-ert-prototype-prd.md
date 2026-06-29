# Product Requirements Document: AIoT-Ready Phase 3A DC ERT Prototype

## Problem Statement

The repo contains multiple generations of an Electrical Resistance Tomography prototype, but the project still needs one coherent product definition that ties together the working hardware, firmware, acquisition scripts, offline analysis, reconstruction flow, and validation workflow. Right now, the prototype can already perform meaningful acquisition and early reconstruction work, but the repo spans legacy Phase 2 fixed-injection scanning, newer Phase 3A 12-electrode switched measurements, thesis-oriented validation documents, and several reconstruction scripts with different protocol assumptions. Without a single PRD, it is easy to overclaim what the prototype can do, miss critical validation steps, or change one part of the stack without keeping the rest aligned.

The user needs a defensible, student-realistic product target that uses the actual components already present in the repo, preserves honest limits, and defines what "working prototype" means before any stronger health-classification or field-diagnosis claims are made.

## Solution

Build and stabilize an AIoT-ready Phase 3A DC ERT prototype centered on the current 12-electrode switched architecture while preserving the legacy Phase 2 tools as support utilities rather than pretending they are the final path. The product should provide:

- a breadboard-first 12-electrode DC ERT hardware stack using the existing controller, DAC, ADC, current-source, and four-mux switching approach;
- firmware that emits complete, quality-tagged adjacent or opposite measurement frames;
- Python acquisition and reconstruction tooling that can parse those frames, normalize transfer resistance using forward and reverse polarity measurements, validate baseline stability, and save raw logs plus reconstruction outputs;
- offline analysis utilities for legacy exports and for future PyEIT-style preparation;
- a validation ladder that starts with dummy loads and saline phantoms, then moves toward trunk samples and standing living coconut tree observations;
- a thesis-safe output story: repeatable acquisition, approximate conductivity-variation localization, and classifier-ready feature generation, without claiming disease diagnosis.

## User Stories

1. As a student researcher, I want one product definition for the prototype, so that hardware, firmware, Python, and thesis work all target the same outcome.
2. As a builder, I want the prototype to use the components already present in the repo, so that I can keep progressing without redesigning the whole system first.
3. As a hardware integrator, I want the ESP32-S3 to control all switching and measurement peripherals, so that one controller coordinates the complete scan flow.
4. As a hardware integrator, I want the MCP4725 to set the current-source command level, so that the injected current can be adjusted in a controlled way.
5. As a hardware integrator, I want the ADS1115 to measure both electrode voltage and return-shunt voltage, so that the system can record voltage response and estimate injected current.
6. As a hardware integrator, I want the OPA2134-based improved Howland current pump to drive the source path, so that the prototype can inject usable microamp-level current instead of relying on the weaker earlier LM358 stage.
7. As a hardware integrator, I want four CD74HC4067 muxes to switch current source, current return, voltage positive, and voltage negative independently, so that the system can capture reconstruction-capable measurements.
8. As a hardware integrator, I want a 12-electrode ring labeled E1 through E12, so that the acquisition geometry matches the intended Phase 3A reconstruction workflow.
9. As a firmware developer, I want the serial protocol to emit complete frame records with pattern, DAC code, settling time, sample count, polarity, current pair, voltage pair, voltage, current, and quality, so that the Python side can parse and validate the data reliably.
10. As a firmware developer, I want adjacent and opposite drive patterns selectable at runtime, so that I can compare practical measurement behavior without reflashing.
11. As a firmware developer, I want forward and reverse injection records in each frame, so that the reconstruction tool can reduce polarity bias and normalize transfer resistance.
12. As a firmware developer, I want explicit idle behavior that forces DAC output to zero and disables muxes, so that the hardware is safer when not scanning.
13. As a bench tester, I want I2C diagnostics for the MCP4725 and ADS1115, so that I can stop early when wiring or grounding faults break the basic hardware chain.
14. As a bench tester, I want direct dummy-load validation before phantom testing, so that I can confirm current range and shunt behavior before trusting scanned measurements.
15. As a bench tester, I want the firmware and docs to preserve the 100-ohm shunt assumption unless intentionally changed everywhere, so that printed current values stay meaningful.
16. As a bench tester, I want the system to flag low, high, reversed, or out-of-range measurements, so that bad analog behavior is treated as a hardware problem instead of reconstruction evidence.
17. As a Python user, I want the unified reconstruction script to open the serial port, configure the board, capture warmup frames, collect baseline frames, and then run comparison or control captures, so that I can execute a complete measurement session from one command.
18. As a Python user, I want baseline stability checks before reconstruction, so that noisy or drifting data is rejected before it produces misleading images.
19. As a Python user, I want control-mode drift analysis without moving the target, so that I can distinguish contact drift from a real anomaly response.
20. As a Python user, I want reconstruction output images and raw CSV logs saved for each run, so that every experiment leaves a reviewable artifact trail.
21. As a Python user, I want run metadata such as pattern, DAC, settling time, sample count, and frame identifiers preserved in logs, so that I can compare runs honestly.
22. As a Python user, I want the software to compute paired transfer resistance from forward and reverse measurements, so that the reconstruction vector is based on a more stable electrical quantity.
23. As a Python user, I want the system to support a baseline-versus-target difference workflow, so that the reconstructed images reflect relative conductivity variation rather than pretending to be absolute maps.
24. As a researcher, I want adjacent-pattern runs to be the default practical mode, so that the first validation path stays simple and repeatable.
25. As a researcher, I want opposite-pattern runs available for comparison, so that I can test whether they provide useful information or reveal hardware weaknesses.
26. As a researcher, I want per-frame current summaries during capture, so that I can notice when the prototype has dropped into unusably low current.
27. As a researcher, I want the average reconstruction over multiple frames saved separately, so that I can rely more on repeatable trends than on single-frame artifacts.
28. As a researcher, I want the software to highlight the most unstable electrodes and measurement pairs in control mode, so that debugging can target the weakest parts of the ring.
29. As a researcher, I want offline analysis tools for older Phase 2 exports, so that earlier scans are still useful for stability and delta exploration without pretending they are full tomography.
30. As a researcher, I want a PyEIT-preparation path that stays honest about hardware completeness, so that I can explore reconstruction methods without faking measurement validity.
31. As a researcher, I want legacy Phase 2 acquisition to remain available as a simpler scanning tool, so that the repo preserves the progression from fixed-injection scanning to switched reconstruction hardware.
32. As a documentation user, I want a clear distinction between legacy Phase 2 assumptions and active Phase 3A behavior, so that I do not wire or parse the system incorrectly.
33. As a documentation user, I want the repo to explain safe grounding and rail usage clearly, so that I do not accidentally tie the op-amp negative rail to logic ground incorrectly.
34. As a documentation user, I want the repo to explain that all analog pins must remain inside safe mux and ADC voltage range, so that I do not damage parts or collect nonsense data.
35. As a thesis writer, I want the product language to describe a proof-of-concept ERT prototype rather than a diagnostic device, so that the written claims stay defensible.
36. As a thesis writer, I want the repo to support a validation ladder from dummy loads to saline phantom to trunk samples to standing living coconut trees, so that field claims are built on staged evidence.
37. As a thesis writer, I want field terminology such as healthy tree, asymptomatic tree, diseased tree, conductivity variation pattern, and expert evaluation used consistently, so that the thesis narrative stays aligned with the intended study framing.
38. As a thesis writer, I want the prototype to produce classifier-ready raw and reconstruction-derived features, so that later AI-assisted classification work has a grounded acquisition source.
39. As a field operator, I want an offline-first workflow where scan data is captured locally first, so that poor connectivity does not block measurements.
40. As a field operator, I want the architecture to remain compatible with a future Raspberry Pi field computer and later Google Drive synchronization, so that the laptop-based workflow can evolve into the intended AIoT deployment.
41. As a field operator, I want experimental outputs such as logs, stability reports, and reconstruction images organized predictably, so that tree or phantom runs can be reviewed later.
42. As a maintainer, I want protocol parsing, frame normalization, drift analysis, and export loading separated into testable behavior-focused modules, so that the code can be changed incrementally without breaking the whole workflow.
43. As a maintainer, I want firmware, reconstruction logic, offline analysis, and documentation to stay behaviorally aligned, so that a change in one layer does not silently invalidate another.
44. As a maintainer, I want tests to lock down the serial frame contract and the measurement normalization behavior, so that future edits do not corrupt the reconstruction pipeline.
45. As a maintainer, I want the repo to record known blockers like shunt mismatch, weak current, channel outliers, or bad contact sectors, so that debugging work stays focused on real bottlenecks.
46. As a reviewer, I want the prototype's success criteria to emphasize repeatable acquisition and approximate localization, so that the project is judged on what it currently can do.
47. As a reviewer, I want the project to reject claims of absolute conductivity mapping, disease detection, or anatomy-confirmed imaging, so that the prototype is evaluated honestly.
48. As a future developer, I want a path to extend the current stack toward stronger AIoT storage, dataset building, and classification-ready features, so that the repo can grow without rewriting its foundations.

## Implementation Decisions

- The product target is the active Phase 3A 12-electrode switched DC ERT prototype, while legacy Phase 2 tools remain in scope as supporting utilities for earlier scanning and export analysis.
- The hardware baseline uses ESP32-S3, MCP4725, ADS1115, OPA2134-based improved Howland current source, four CD74HC4067 muxes, a return shunt, and a 12-electrode ring.
- The primary system claim is repeatable acquisition plus approximate conductivity-variation localization from difference reconstruction, not diagnostic tree-health determination.
- The firmware contract centers on full frame records that include drive pattern, acquisition parameters, paired forward and reverse measurements, measured voltage, measured current, and a quality flag.
- The software architecture should treat protocol parsing, frame validation, transfer-resistance normalization, baseline stability assessment, control drift analysis, reconstruction orchestration, and raw log writing as separate deep modules with narrow interfaces.
- The reconstruction workflow should normalize using forward and reverse polarity records and produce difference images relative to a tree-specific or phantom-specific baseline rather than attempting absolute conductivity estimation.
- The active runtime modes are adjacent-pattern reconstruction, opposite-pattern reconstruction, and control drift runs; all should share the same validated frame parser and logging core.
- Current-quality gating is a product feature, not optional debugging. Non-OK measurements and near-zero current should block trust in the output instead of being quietly tolerated.
- The product must preserve a clear split between active Phase 3A protocol handling and legacy Phase 2 `SCAN:`-style handling to avoid mixed assumptions.
- Offline analysis of Phase 2 exports remains valuable for stability summaries and dataset preparation, but it must not be presented as proof of full tomography completeness.
- Run artifacts should include raw logs, reconstruction images, average reconstruction summaries, and control stability reports so a session can be audited after capture.
- The validation ladder is part of the product definition: dummy load, mux-path checks, saline phantom, movable phantom object, trunk pilot, and only then observational living-tree scans.
- The field-thesis layer is in scope as documentation and workflow framing: classifier-ready features, expert-evaluated category labels, offline-first acquisition, and future Raspberry Pi plus cloud sync compatibility are requirements, but validated classification performance is not.
- The product should continue using thesis-safe glossary terms across docs and outputs so that the repo narrative stays aligned with a proof-of-concept academic prototype rather than a finished diagnostic instrument.

## Testing Decisions

- Good tests should verify external behavior and contracts, not internal implementation details. For this repo, that means testing what records are accepted or rejected, what vectors and summaries are produced from known inputs, what artifacts are written, and what user-visible command behavior is preserved.
- The serial frame parser should be tested with valid adjacent and opposite headers, malformed records, missing forward or reverse pairs, bad quality flags, and mismatched frame terminators.
- The measurement-normalization layer should be tested with known forward and reverse synthetic records to confirm transfer-resistance calculations and expected vector ordering.
- The baseline-stability and control-drift logic should be tested with stable, unstable, and edge-case datasets so that threshold enforcement is intentional and reviewable.
- The reconstruction orchestration layer should be tested at the behavior level for argument validation, log-path generation, control-mode output generation, and interactions around baseline versus comparison capture.
- The legacy export analyzer should be tested for CSV and NPZ loading, summary statistics, and measurement-matrix generation so Phase 2 artifacts remain trustworthy support inputs.
- The firmware-facing protocol layer should be tested through contract fixtures that mirror actual serial lines, since the most important failure mode is parser drift between board output and Python expectations.
- Prior art already exists in the repo’s current unit-test style around legacy acquisition behavior, Phase 3A reconstruction helpers, unified firmware parsing, and offline analyzer utilities, so new tests should follow that pattern of deterministic, hardware-free validation.
- Hardware validation remains essential and cannot be replaced by unit tests. Required bench verification includes I2C detection, safe idle behavior, shunt verification, dummy-load current measurements, mux-path continuity, and stable control runs before trusting any reconstruction image.

## Out of Scope

- Claiming validated disease diagnosis or decay detection from the current prototype.
- Claiming absolute conductivity imaging or anatomically confirmed internal maps.
- Replacing the entire analog stack with a new high-end impedance platform in this phase.
- Treating a single reconstruction image as sufficient proof of performance.
- Skipping dummy-load, phantom, or control validation and moving directly to tree claims.
- Declaring the classifier component validated from the current repo contents alone.
- Requiring cloud connectivity during acquisition.
- Dropping legacy Phase 2 tools entirely; they are not the final product, but they remain useful and should not be erased from the repo story.

## Further Notes

- The repo currently spans two truths that must both be preserved: the older Phase 2 fixed-injection scanner is real and useful, and the active product target has moved to the Phase 3A 12-electrode switched architecture.
- The most immediate technical risk is not visualization polish but measurement repeatability: grounding, shunt correctness, current magnitude, contact quality, mux-path health, and protocol consistency.
- Success should be judged by whether the system can repeatedly acquire stable frames, pass control-mode drift checks, and show an average reconstruction that moves in a reasonable way when a known phantom target is moved.
- If issue-tracker publication is needed later, this PRD is ready to be copied into a tracker item and labeled for triage, but the current environment does not expose a tracker publishing tool.
