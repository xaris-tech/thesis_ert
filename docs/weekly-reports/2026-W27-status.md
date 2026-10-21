# Weekly Status Report — 2026-W27 (29 June – 5 July 2026)

**Project:** Low-cost 12-electrode DC ERT prototype for coconut trees

## 1. Summary

A software-heavy week. Skip-1 and skip-2 drive patterns were added alongside adjacent and
opposite, and the Tkinter debug UI was built in a few days: settings model, acquisition
layer, live hardware progress, reconstruction previews, control-drift analysis and a
drift-tuning loop.

## 2. Circuit construction

No change recorded.

## 3. Testing and verification

- Consistency filtering added to reconstruction: measurements that fail health checks are
  flagged before solving.
- Control-drift analysis: a repeated capture with nothing changed measures how much the
  instrument drifts on its own.
- Drift tuning: sweeps settle time, sample count, warmup and baseline count and picks the
  setting with the lowest drift.

## 4. Scans

No recorded scans. The debug UI can now capture baseline, control and target runs against
real hardware or a demo source.

## 5. Difference imaging

The UI shows baseline and repeated reconstruction previews, and live target
reconstructions.

## 6. Absolute imaging

No change.

## 7. Saline tank

No change.

## 8. Resistor ring

No change.

## 9. Wood discs

No change.

## 10. 3D-printed case

*Not recorded in the repository. To be filled in.*

## 11. Risks and blockers

None recorded. (The current-sense miswire found in W36 was already present, but not yet
known.)

## 12. Plan for next week

Bench-test the full chain on hardware.

*Next: weeks W28–W34 cover the 3D-printed case.*
