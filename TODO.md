# Project TODO List

Planned firmware and GUI improvements from the 2026-08-27 bench session are tracked
separately in [docs/planned-improvements.md](docs/planned-improvements.md), including the
measured findings that motivate them (low current-pump output impedance, electrode
polarisation in saline, forward/reverse offset domination). See that file's Status section
for what has landed — most of F1-F5, F8 and the R-series are done; F6, F7 and the Tier 3/4
host items are not.

Separately, [docs/validity-audit.md](docs/validity-audit.md) records the 2026-08-27 independent
review. Its findings are not duplicated below; work items arising from it are listed there in
recommended order. All five confirmed defects (D-01..D-05) are now fixed; what remains are the
three hardware limits (L-01..L-03) and the documentation items X-01/X-02.

## Hardware & Physical Setup
- [ ] Make proper alligator clips with alligator on one end and wire on the other.
- [x] Verify and document the real shunt value, then sync the firmware constant and docs.
  Measured 97.9 ohm on 2026-08-27; firmware `DEFAULT_SHUNT_OHMS` is now `97.9f` (F4, done).
- [ ] **Measure two-nail inter-electrode resistance on a real coconut palm** (validity-audit
  L-01, 5 minutes with a multimeter, do before more software work on the current path):
  1. Push two nails/probes into the trunk at roughly the electrode spacing used on the ring
     (or use two adjacent ring electrodes directly) and read resistance directly with a
     multimeter in ohms mode.
  2. Compare against this table (from `docs/validity-audit.md` L-01 — ceiling is
     `3.3V / R_tree`, since both mux ICs are 3.3V-rail CD74HC4067 parts):

     | Measured R | Ceiling on delivered current | Verdict |
     |---:|---:|---|
     | ~10 kohm | ~330 uA | workable |
     | ~30 kohm | ~110 uA | marginal |
     | ~100 kohm | ~33 uA | below the ~100 uA usable floor (`HANDOVER.md`) |
  3. If R lands at/above ~30-100 kohm on living tissue, L-01 is a redesign, not a footnote:
     next step is a higher mux rail (CD74HCT4067 at 5V) or a different analog-switch family,
     not a firmware change. Record the measured R and verdict in `docs/validity-audit.md`
     under L-01's status once done.
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
