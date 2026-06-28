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

**Tree-specific baseline**:
The reference scan collected from the same coconut tree and electrode setup before interpreting difference reconstructions for that tree.
_Avoid_: healthy-tree baseline, cross-tree baseline

**Twelve-electrode ring**:
The field electrode layout using 12 nail electrodes placed around the coconut trunk and labeled E1 through E12.
_Avoid_: eight-electrode ring, fixed-injection layout

**Electrode sector**:
A coarse localization region described by nearby electrode labels in the twelve-electrode ring, such as near E3-E4, used instead of exact image coordinates.
_Avoid_: exact lesion coordinate, pixel-perfect location

**Provisional field current range**:
The planning target of 100-500 uA, with about 300 uA as an initial target, to be confirmed on dummy loads and actual coconut trees before final acceptance.
_Avoid_: guaranteed tree current, fixed biological threshold

**Validation ladder**:
The staged prototype validation path from dummy loads, to saline phantom, to cut-trunk pilot, to final three-tree comparison.
_Avoid_: direct field validation, one-step tree testing

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
A cut coconut trunk section used to test electrode placement, current settings, and scanning procedure before the final standing living coconut tree comparison.
_Avoid_: final category tree, living-tree result

**Artificial trunk defect**:
A deliberately cut internal region in the cut-trunk pilot used to test whether the prototype can show a repeatable conductivity variation near a known sector.
_Avoid_: natural disease, confirmed decay

**Top-drilled defect**:
An artificial trunk defect created from the cut face by drilling or hollowing into the interior while preserving the outer electrode ring.
_Avoid_: side-cut defect, external wound proxy

**Side-sector defect**:
A top-drilled defect positioned near a known electrode sector to test coarse localization.
_Avoid_: center-only defect, unlocated defect

**Center defect**:
A top-drilled defect positioned near the center of the cut-trunk pilot to test response to central internal variation.
_Avoid_: side-sector defect, electrode-contact defect

**Cut-trunk before-after scan**:
The pilot sequence where the same cut trunk is scanned intact, then after a side-sector defect, then after a center defect.
_Avoid_: unpaired defect scan, post-only defect scan

**Observational living-tree scan**:
The final field scan method for standing living coconut trees, using only minimally invasive nail electrodes and no drilling or hollowing.
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
The classifier input made from both normalized raw ERT measurements and reconstruction-derived summary features.
_Avoid_: image-only classifier, raw-only classifier

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
