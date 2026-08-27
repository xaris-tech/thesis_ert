# Project TODO List

Planned firmware and GUI improvements from the 2026-08-27 bench session are tracked
separately in [docs/planned-improvements.md](docs/planned-improvements.md), including the
measured findings that motivate them (low current-pump output impedance, electrode
polarisation in saline, forward/reverse offset domination). None of those items are
implemented yet.

Separately, [docs/validity-audit.md](docs/validity-audit.md) records the 2026-08-27 independent
review. Its findings are not duplicated below; work items arising from it are listed there in
recommended order.

## Hardware & Physical Setup
- [ ] Make proper alligator clips with alligator on one end and wire on the other.
- [ ] Verify and document the real shunt value (10 vs 100 ohm), then sync the firmware constant and docs. Measured 97.9 ohm on 2026-08-27; firmware constant is still 100.0 (see F4).
- [ ] Investigate E9/E10 outlier voltage pairs (check E9/E10 electrode contact, channel wiring, `MUX_VP`/`MUX_VN` channels `C8/C9`, and alligator clips).
- [ ] Debug low or zero current paths (e.g., E9 return path) and test mux channels electrically if needed.

## Firmware
- [ ] Add a simple serial/I2C diagnostic firmware command if not already present.

## Python Software & Logging
- [ ] Add a per-electrode/per-current-pair health report in the Python script.
- [ ] Improve logs so every run records DAC, shunt value, current median, diameter label, pattern, and stability summary.

## Validation & Testing
- [ ] Create a validation dataset: control, target near E11/E12, target near E2/E3, target near center.
- [ ] Compare average reconstruction location against known target location to ensure approximate localization accuracy.
