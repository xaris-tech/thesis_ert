# DC ERT Coconut Tree Prototype

This context defines thesis domain language for the Phase 3A DC Electrical Resistance Tomography prototype intended for controlled testing on standing living coconut trees.

## Language

**Proof-of-concept ERT prototype**:
A low-cost DC Electrical Resistance Tomography system judged by repeatable acquisition and approximate conductivity-variation localization, not by disease diagnosis.
_Avoid_: diagnostic device, disease detector

**Standing living coconut tree**:
A live coconut tree tested in place, with electrodes placed around its trunk rather than on a cut trunk section.
_Avoid_: cut trunk, lab tree sample

**Expert evaluation**:
The Philippine Coconut Authority expert process used to classify a tested coconut tree as healthy, asymptomatic, or diseased before comparing reconstruction results.
_Avoid_: visual guess, ERT diagnosis

**Healthy tree**:
A standing living coconut tree assessed by expert evaluation as having no visible symptoms and no specific reason for suspected internal degradation.
_Avoid_: normal tree

**Asymptomatic tree**:
A standing living coconut tree with no visible external decay but identified through expert evaluation as having possible hidden disease, damage, or degradation risk.
_Avoid_: healthy tree

**Diseased tree**:
A standing living coconut tree with visible symptoms or expert-observed indicators consistent with disease or internal degradation.
_Avoid_: confirmed decayed tree, ERT-diagnosed tree

**Conductivity variation pattern**:
A repeatable reconstruction pattern produced by the ERT prototype that indicates relative electrical variation inside the scanned trunk band, not a named disease.
_Avoid_: disease detection, disease classification

**Imaging baseline**:
The bench reference scan captured from an unchanged sample, subtracted from a later scan of the same sample to form a difference reconstruction. Valid only where the same physical sample can be scanned before and after a deliberate change.
_Avoid_: field baseline, tree-specific baseline, cross-tree baseline

**Field QA baseline**:
The repeated reference scan captured on a standing living coconut tree to prove acquisition stability for that session. It admits or rejects the session's data and is never subtracted to produce a tree image.
_Avoid_: imaging baseline, tree-specific baseline, difference reference

**Session admission**:
The decision to accept or discard a standing living coconut tree's scan session based on whether its field QA baseline held stable.
_Avoid_: image validation, reconstruction gate

**Twelve-electrode ring**:
The field electrode layout using 12 stainless steel screw electrodes placed around the coconut trunk and labeled E1 through E12.
_Avoid_: eight-electrode ring, fixed-injection layout

**Electrode sector**:
A coarse localization region described by nearby electrode labels in the twelve-electrode ring, such as near E3-E4, used instead of exact image coordinates.
_Avoid_: exact lesion coordinate, pixel-perfect location

**Provisional field current range**:
The planning target of 100-500 uA, with about 300 uA as an initial target, to be confirmed on dummy loads and actual coconut trees before final acceptance.
_Avoid_: guaranteed tree current, fixed biological threshold

**Validation ladder**:
The staged prototype validation path from dummy loads, to saline phantom, to cut-trunk pilot, to the standing-tree field study. The cut-trunk pilot is where the device is verified against known ground truth; the field study begins only after it passes.
_Avoid_: direct field validation, one-step tree testing, three-tree comparison

**Standing-tree field study**:
The open-ended field stage in which expert-evaluated standing living coconut trees are scanned to compare health categories, sized by how many trees the Philippine Coconut Authority can provide rather than by a fixed count.
_Avoid_: three-tree comparison, fixed-sample field study

**Dummy-load verification**:
The bench validation step where known resistor loads and multimeter readings are used to confirm current output before phantom or tree testing.
_Avoid_: tree-first calibration, serial-only calibration

**Direct dummy-load path**:
The initial calibration wiring where the current source drives a known resistor and 100 ohm shunt directly, before testing through the electrode muxes.
_Avoid_: mux-first calibration, full-system-first calibration

**Saline phantom**:
A controlled conductive container used to test electrode switching, baseline stability, and reconstruction response before coconut tree scanning.
_Avoid_: tree substitute, final validation sample

**Movable phantom object**:
A known object placed at different sectors in the saline phantom to check whether reconstruction changes move with the object.
_Avoid_: disease proxy, decay proof

**Plastic phantom target**:
A non-conductive object placed in the saline phantom as the primary movable contrast target.
_Avoid_: disease sample, biological target

**Cut-trunk pilot**:
A cut coconut trunk section used to verify the prototype against known ground truth before the standing-tree field study, by scanning defects whose position and size are chosen by the operator.
_Avoid_: final category tree, living-tree result

**Sector-varied trunk set**:
The set of cut-trunk pilots run through an identical defect ladder while the drilled sector differs on each trunk, so that correct localization cannot be explained by a fixed directional bias.
_Avoid_: repeated identical pilot, single-sector validation

**Held-constant protocol**:
The requirement that every factor other than the drilled sector stays identical across the trunk set, covering electrode count, drive patterns, defect sizes, session structure, and acquisition settings.
_Avoid_: per-trunk tuning, adaptive protocol

**Artificial trunk defect**:
A deliberately cut internal region in the cut-trunk pilot used to test whether the prototype can show a repeatable conductivity variation near a known sector.
_Avoid_: natural disease, confirmed decay

**Top-drilled defect**:
An artificial trunk defect created from the cut face by drilling or hollowing into the interior while preserving the outer electrode ring. It must extend at least one electrode spacing below the electrode band so that it crosses the measurement plane.
_Avoid_: side-cut defect, external wound proxy

**Detection threshold defect**:
The smallest top-drilled defect in the ladder, sized near the resolution limit of the twelve-electrode ring, used to find the point at which the prototype stops detecting a known anomaly.
_Avoid_: guaranteed-visible defect, calibration defect

**Side-sector defect**:
A top-drilled defect positioned near a known electrode sector to test coarse localization.
_Avoid_: center-only defect, unlocated defect

**Center defect**:
A top-drilled defect positioned near the center of the cut-trunk pilot to test response to central internal variation.
_Avoid_: side-sector defect, electrode-contact defect

**Cut-trunk before-after scan**:
The pilot sequence where the same cut trunk is scanned at four defect stages: intact, small side-sector defect, enlarged side-sector defect, and added center defect.
_Avoid_: unpaired defect scan, post-only defect scan

**Absolute reconstruction**:
The reconstruction of a single scan against a modelled uniform trunk rather than against an earlier scan of the same subject, producing a per-tree conductivity variation pattern without any time baseline.
_Avoid_: difference reconstruction, baseline-referenced image

**Measured trunk model**:
The forward model built for each scanned subject from its measured circumference and the recorded actual positions of the twelve screw electrodes, replacing the dimensionless unit circle.
_Avoid_: unit circle mesh, assumed electrode spacing

**Signal-referenced stability gate**:
The baseline stability limit derived from the measured size of a known phantom target response, requiring session drift to stay a stated factor below it.
_Avoid_: fixed percentage gate, inherited threshold

**Reference target response**:
The measured change in transfer resistance produced by moving the plastic phantom target between known positions, used as the signal scale that the stability gate is set against.
_Avoid_: expected signal, assumed contrast

**Unbroken electrode ring**:
The rule that the twelve-electrode ring is installed once on the cut-trunk pilot and is never removed, moved, or re-seated until all four defect stages are scanned.
_Avoid_: reinstalled ring, per-stage electrode setup

**Single-session ladder**:
The requirement that all four defect stages of the cut-trunk pilot are drilled and scanned within one continuous working session, so that trunk moisture loss cannot accumulate between stages.
_Avoid_: multi-day ladder, staged-over-time pilot

**Stage-labelled run**:
A scan run that carries its specimen identity and defect stage inside the recorded data itself, so that a stage can never be inferred from a filename or a timestamp.
_Avoid_: timestamped run, renamed log

**Cut-trunk data sheet**:
The written record kept per defect stage holding the run identifier, hole dimensions, drill depth, elapsed session time, and any contact problems observed.
_Avoid_: field data sheet, tree information sheet

**Defect stage**:
One permanent physical state of the cut-trunk pilot, scanned in full before the next defect is cut. Stages are cumulative and cannot be undone or revisited.
_Avoid_: defect trial, repeatable condition

**Dual-pattern stage scan**:
The rule that every defect stage is captured with both the adjacent and the opposite drive pattern, so that each pattern has a matching previous stage to difference against.
_Avoid_: pattern-per-stage, supplemental opposite run

**Stage-to-stage difference**:
The difference reconstruction between one defect stage and the stage immediately before it, which isolates the single defect newly added at that step.
_Avoid_: intact-referenced difference, cumulative difference

**Sector match criterion**:
The pre-registered success test for the cut-trunk pilot, requiring the strongest reconstruction sector to match the drilled sector in at least two of three repeat runs at a given defect stage.
_Avoid_: post-hoc success test, visual agreement

**Exploratory stage**:
A defect stage whose outcome is declared informative in advance whether or not the defect is detected, because it probes the resolution limit rather than testing a claim.
_Avoid_: failed stage, inconclusive run

**Category proxy stage**:
A defect stage used as a bench stand-in for a coconut tree health category, providing labelled data for the classifier without any claim that the stage is that category.
_Avoid_: healthy sample, asymptomatic sample, diseased sample

**Observational living-tree scan**:
The final field scan method for standing living coconut trees, using only minimally invasive screw electrodes and no drilling or hollowing.
_Avoid_: living-tree defect creation, destructive field test

**Field permission document**:
A documented arrangement with the Philippine Coconut Authority and coconut tree owners authorizing minimally invasive field testing.
_Avoid_: informal access, undocumented tree testing

**Contact-adjustment restart**:
The rule that a bad electrode contact is corrected and documented, then the full scan run is restarted rather than mixing measurements before and after adjustment.
_Avoid_: partial-run repair, undocumented contact change

**Backup category tree**:
An additional expert-evaluated coconut tree in the same category, reserved in case the selected tree cannot produce stable field measurements.
_Avoid_: uncontrolled replacement, post-hoc category swap

**Working thesis title**:
Development of an AIoT-Enabled Electrical Resistivity Tomography (ERT)-Based Tree Health Classification System for Coconut Palm (Cocos nucifera).
_Avoid_: final validated diagnostic claim

**AI-assisted health category classification**:
A downstream classification step that uses complete ERT raw values, reconstruction-derived features, or both to classify expert-defined coconut tree health categories.
_Avoid_: disease diagnosis, classifier without stable reconstruction data

**Combined ERT feature set**:
The small set of physically interpretable summary features describing one scan, drawn from the raw measurement ring profile, reconstruction output, current quality, and run repeatability.
_Avoid_: image-only classifier, raw-only classifier, full-vector input

**Leave-one-trunk-out evaluation**:
The classifier evaluation rule where all scans from one cut-trunk pilot are held out as the test set and the model is trained on the remaining trunks, so that scores reflect performance on a trunk never seen in training.
_Avoid_: random split, per-scan holdout

**Ground-truth label**:
An operator-chosen fact about a cut-trunk scan, being either its defect stage or its drilled sector, known with certainty because the operator created it.
_Avoid_: expert label, predicted category

**Prototype classifier component**:
A future-facing or demonstration AI component whose inputs and pipeline are defined, but whose performance is not claimed as validated from the three-tree dataset.
_Avoid_: validated classifier, production model

**Minimum thesis deliverable**:
A working AIoT-ready ERT prototype that acquires stable 12-electrode field data, produces repeatable difference reconstructions, extracts classifier-ready features, and compares healthy, asymptomatic, and diseased coconut trees using expert labels.
_Avoid_: disease diagnostic product, validated AI classifier

**Offline-first AIoT storage**:
The data handling approach where field scan records are stored locally first and sent to cloud storage when internet connectivity is available.
_Avoid_: cloud-required acquisition, live-only upload

**Raspberry Pi field computer**:
The final-prototype local computer that stores field scan data and performs the role currently handled by the laptop-based Python workflow.
_Avoid_: ESP32-only storage, cloud-required controller

**USB serial acquisition link**:
The first final-prototype connection where the ESP32-S3 sends scan records to the Raspberry Pi over USB serial.
_Avoid_: Wi-Fi-first acquisition, cloud-first acquisition

**Google Drive field sync**:
The cloud synchronization target where Raspberry Pi field outputs are uploaded after local acquisition when internet is available.
_Avoid_: custom dashboard requirement, cloud-only storage

**Safe success claim**:
The claim that the AIoT-ready DC ERT prototype acquired repeatable 12-electrode measurements from coconut palm samples and standing living coconut trees, produced difference reconstructions showing category-associated conductivity variation patterns, and generated classifier-ready features for future health-category classification.
_Avoid_: confirmed disease detection, validated diagnostic classifier
