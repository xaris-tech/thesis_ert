# ADR-0036: Specimen presets carry their provenance

- **Status:** Accepted
- **Date:** 2026-09-23
- **Affects:** `tree_ert/settings.py`, `tree_ert/qt/main_window.SettingsPanel`, and what an
  operator can tell about the settings a run was captured at
- **Related:** the cohort settings lock is
  [ADR-0035](0035-intact-disc-survey-measures-between-specimen-spread.md); DAC ceilings from
  [ADR-0011](0011-current-guard-derives-from-fitted-rs.md); provenance discipline from
  [ADR-0023](0023-per-run-folders-with-a-conditions-sheet.md)

## Context

The rig is used on three classes of specimen — a resistor belt, a saline tank, and coconut
material — and the operator sets the instrument by hand each session. All 95 runs recorded to date
used one profile: `adjacent / high / dac 400 / 30 ms / 16 samples / 5 warmup / 10 frames`. The
results were not equivalent:

```text
specimen          reciprocity median    noise
resistor belt              0.1 %        0.14 %
coconut                    3.7 %        0.79 %
purified saline           10-15 %       1.0 %
```

The belt is the instrument's own floor. The saline tank is the worst of the three, being
offset-dominated. Coconut sits between them and has never been tuned — 2026-09-23's tree runs used
these values because they were already set, not because anything showed them suitable.

ADR-0035 requires a settings profile locked across a cohort, with a disc excluded rather than
retuned, because changing DAC or current range mid-cohort introduces a variable the normalisation
does not cancel and no gate catches. Retyping five fields per session is how that lock gets broken
by accident.

A preset that is only a set of numbers creates a different problem. An operator picking "Coconut"
from a menu reasonably reads it as a validated profile. For coconut that is currently false.

## Decision

`tree_ert/settings.py` gains `SpecimenPreset` and `SPECIMEN_PRESETS` for the three specimen
classes. Each preset records the run its numbers came from and what that run measured, and carries
a `validated` flag that is `False` for coconut until it is tuned. `apply_to` moves only instrument
fields; port, demo mode, scans root and electrode mapping are left alone. The panel shows the
matching preset's provenance, falls back to "Custom" the moment any field is edited, and re-selects
a preset if edits land back on it.

## Rationale

**Why presets live in `settings.py` and not the widget.** They are domain facts about which
profile suits which specimen, they need testing without a Qt event loop, and the project's rule is
that computed values do not live inside widgets. `SpecimenPreset.apply_to` and `matching_preset`
are pure functions over `UiSettings`.

**Why provenance is a required field rather than a comment.** A profile with no stated origin is a
guess that reads as a measurement. A test asserts every preset has one, so a future preset added
without provenance fails the suite rather than shipping.

**Why coconut is offered at all when it is not validated.** It is better than the bare defaults —
`UiSettings` defaults to `dac=100, samples=4`, which is far from anything that has worked — and
the profile is about to be tuned. Marking it `PROVISIONAL` in the panel keeps the offer honest.

**Why three entries when the values are currently identical.** They differ in provenance and in
validation status, which is the information the operator needs. The values are expected to diverge
as soon as coconut is tuned; collapsing them into one entry today would have to be undone
tomorrow, and would meanwhile assert an equivalence the reciprocity figures above contradict.

**Why editing falls back to "Custom" rather than leaving the name displayed.** A combo still
reading "Resistor belt" after the settle time was changed claims a provenance the settings no
longer have. The match is recomputed rather than latched, so an edit that returns to a preset's
values re-selects it — the alternative would strand the operator in "Custom" after an undo.

**Why the preset does not touch port, demo mode or electrode mapping.** Those are properties of
the rig and the session, not the specimen. A preset that reset the port, or silently cleared an
`electrode_offset` established from a ground-truth run, would be a trap.

**Known imperfection.** Nothing ties a preset to the `specimen_id` recorded in conditions, so an
operator may scan a disc with the saline preset selected and nothing will object. The two live in
different panels and neither checks the other.

## Consequences

**Easier.** Restoring a cohort profile is one selection instead of five fields, which is what
ADR-0035's settings lock needs in practice. The provenance line puts the evidence for a profile
in front of the operator at the moment of choosing it.

**Harder.** Presets are now another thing to keep truthful. A profile tuned at the bench and not
written back leaves the preset stating an out-of-date provenance, which is worse than no preset,
because it carries authority.

**Committed to.** Every preset states its origin. The coconut preset stays `validated=False` until
a tuning session produces a profile and a run id to cite, at which point both the values and the
provenance string are updated together.

**Will bite later.** The preset and the recorded `specimen_id` can disagree, and neither warns.
Once the survey exists, a mismatch between the selected preset and the specimen actually scanned is
the kind of thing that should be caught at capture time rather than found in analysis.

## Verification

- `tests/test_tree_ert_settings.SpecimenPresetTests` covers that every preset states provenance,
  that all three classes are offered, that coconut is marked provisional, that `apply_to` preserves
  port, log dir and electrode offset, that an applied preset matches itself, that an edited profile
  matches none, that each preset respects its range's DAC ceiling and passes `validate()`.
- `tests/test_tree_ert_qt.SettingsPanelPresetTests` covers the combo pushing values into the
  fields, keeping the port, falling back to Custom on an edit, re-selecting on an undo, showing
  `PROVISIONAL` for coconut, showing a run id for a validated preset, and Custom being inert.
- In force when the panel's Preset row shows a provenance line naming a run id.
- Falsified if a tuned coconut profile is adopted at the bench without its preset being updated,
  which would mean the provenance mechanism is not load-bearing in practice.
