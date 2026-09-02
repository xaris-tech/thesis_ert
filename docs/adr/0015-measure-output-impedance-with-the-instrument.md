# ADR-0015: Measure output impedance with the instrument's own shunt, not a multimeter

- **Status:** Accepted
- **Date:** 2026-09-02
- **Affects:** the `d` (debug hold) firmware command, the new `HOLD` serial record,
  `dummy_load_sweep.py`, `docs/current-setup-validation-runbook.md` section 4, and the
  outstanding output-impedance verification in
  [ADR-0014](0014-current-sense-feedback-tapped-before-rs.md)
- **Related:** [ADR-0014](0014-current-sense-feedback-tapped-before-rs.md),
  [ADR-0011](0011-current-guard-derives-from-fitted-rs.md),
  [ADR-0003](0003-reciprocity-as-report-not-gate.md),
  [ADR-0010](0010-reciprocity-error-scales-with-signal.md),
  `docs/i-sat-investigation-2026-09-02.md` sections 7.3 and 10.4

## Context

ADR-0014 repaired the current-sense feedback and verified that the current now tracks the DAC
code linearly at 1.531 uA/code against a designed 1.580. That establishes the loop closes. It
does **not** establish that the output impedance is adequate, because every point in that sweep
was taken into the same load — the tree. The measurement that separates a current source from a
voltage source is the same DAC code into *different* loads, and that sweep has never been run on
this rig in its repaired state.

It is the blocking measurement for three separate open items:

- ADR-0014's own Verification section lists it as not performed, so the repair is confirmed
  working but not confirmed sufficient.
- ADR-0010 found reciprocity error rising with signal amplitude and deferred interpretation
  pending dummy loads. A source with finite output impedance delivers a current that depends on
  each drive pair's impedance, which is a candidate mechanism for exactly that.
- The 213 uA offset at zero command (`docs/i-sat-investigation-2026-09-02.md` 10.4) is
  discriminated by the same setup: with the electrodes off and a resistor in their place, a
  near-zero reading at DAC code 0 implicates the electrodes and a reading near 213 uA
  implicates the circuit.

The existing `d` command holds E1/E2 as the drive pair and E3/E4 as sense, prints two
`[DEBUG]` lines, and stops. Reading the current means putting a multimeter on the shunt. The
sweep is a grid of DAC codes crossed with fitted resistors — at four codes and four loads that
is sixteen hand-transcribed readings, taken with the drive live, on a perfboard rig where the
probe hand is next to the thing being characterised.

## Decision

`d` reads the shunt and the sense pair through the instrument's own ADC and emits a
machine-readable `HOLD,1,...` record before handing over to the operator, leaving the muxes
enabled exactly as before. A new host tool `dummy_load_sweep.py` sweeps the DAC codes for one
fitted resistor (`measure`), and fits the Thevenin model `I = Vth / (Rout + Rload)` across the
resistors afterwards (`fit`).

## Rationale

The shunt reading is the right instrument for this measurement, not a compromise for
convenience. Every quality flag, every current normalisation in `paired_transfer_resistance()`,
and therefore every transfer resistance the project reports is computed from that ADC channel.
Characterising the source through a multimeter would measure a signal path the science never
uses, and would leave a shunt-calibration error invisible in exactly the measurement meant to
find it. ADR-0011's `I_SAT` flag rides along for free: a railed channel is now labelled as such
in the sweep data instead of appearing as a plausible number.

Automating it also makes the sweep repeatable. This measurement will be run again after any
change to the analog front end, and a hand-transcribed grid is not something anyone re-runs to
check a regression.

Alternatives considered:

- **Multimeter and a table in the runbook.** Rejected for the reasons above, and because the
  operator has to be at the bench with the drive energised for the duration. The `[DEBUG]` lines
  and the held mux state are retained, so this remains available as a cross-check — and a
  disagreement between the DMM and the `HOLD` line is itself a finding worth having.
- **Stream `HOLD` records continuously while held.** Rejected as more protocol than the problem
  needs. The host sets a code and asks for a reading; a free-running stream would have to be
  started, stopped, and de-duplicated against the codes that produced it.
- **Reuse the `FRAME` path with a resistor across one pair.** Rejected: the other eleven
  electrode pairs are open circuits, which is the condition that latches the amplifier
  (`enterSafeIdle()` presents an open load for the same reason), so most of the frame would be
  `I_SAT` and the run would characterise the latch rather than the source.
- **Bake a flatness pass/fail threshold into the tool.** Rejected under ADR-0003: what counts as
  adequate depends on the spread of load impedances the tree presents, which is not
  characterised. The tool reports Vth, Rout and the peak-to-peak flatness and leaves the verdict
  to the reader.

## Consequences

The firmware and host are coupled by one more record type. `HOLD` is versioned (`HOLD,1,`) and
`parse_hold_line()` rejects an unknown version rather than guessing, but a firmware flashed
before this change emits no `HOLD` line at all — the host raises a `TimeoutError` naming the
reflash, since silently falling back would produce an empty sweep that looks like a measurement.

**The sweep still requires physical work that is not automated and cannot be:** the electrodes
must come off, a resistor must be fitted across E1-E2, and it must be changed between runs. The
rig therefore has to come off the tree, and the tree baselines do not survive that. This ADR
removes the transcription step, not the bench session.

`Rout` is fitted from the same shunt whose calibration `expected_shunt_ohms` exists to check. A
wrong `shuntOhms` scales every current by a constant, which scales `Vth` by that constant and
leaves `Rout` — a ratio of intercept to slope — unaffected. So the impedance result is robust to
shunt error but the absolute current is not, and the self test's shunt check remains the thing
that catches it.

Holding E1/E2 hard-codes which pair is characterised. If output impedance turns out to vary by
pair — which is what would make it the mechanism behind ADR-0010 — this tool measures one pair
and a per-pair variant will be needed.

## Verification

`tests/test_dummy_load_sweep.py` fits the model to synthetic data generated from the 2026-08-27
characterisation (`Rout = 430 ohm`, `Vth = 0.789 V`) and requires it back to three decimal
places; a flat source must return an infinite `Rout` and zero flatness.
`tests/test_phase3a_unified_firmware.py` holds the `HOLD` field names in step with
`parse_hold_line()` and asserts `debugHold()` does not idle the drive.

The bench measurement that would falsify the repair, once the rig is off the tree:

```powershell
.\.venv\Scripts\python.exe dummy_load_sweep.py measure --port COM7 --load-ohms 500
.\.venv\Scripts\python.exe dummy_load_sweep.py measure --port COM7 --load-ohms 1000
.\.venv\Scripts\python.exe dummy_load_sweep.py measure --port COM7 --load-ohms 2000
.\.venv\Scripts\python.exe dummy_load_sweep.py fit phase3a_logs/dummy-load-sweep.csv
```

A repaired current source gives near-flat current across the three loads and an `Rout` far above
2 kohm. Current tracking `1/R_load`, or an `Rout` near 430 ohm, means the repair did not take.
The DAC code 0 row of the same data answers the 213 uA offset question.

**Not yet performed.** The tool and the firmware readout are in place and tested against
synthetic data; no real dummy-load measurement has been taken.
