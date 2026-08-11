# Signal chain changes for measurement stability

Baseline stability failed every tuning preset through July 2026, and more settle time plus more averaging made the best case *worse* (100 ms/16 samples gave 9.20% relative drift; 200 ms/16 gave 18.60%). That pattern points at elapsed-time drift rather than random noise, so the fixes below attack resolution, frame duration, and drift mechanisms rather than adding averaging.

**ADC gain.** The voltage channel ran at `GAIN_ONE` (±4.096 V, 125 µV per count) while real signals sit around 13 mV — a median of 106 counts out of 32,768, with 2.5% of measurements reading exactly zero. Quantisation error alone exceeded the 2% stability limit on 9.8% of measurements. Moved to `GAIN_EIGHT` (±512 mV, 15.6 µV per count): 8× finer, and zero clipping across all 6,480 measurements in the existing logs whose peak was 317 mV. The original code comment tied gain to the 3.3 V mux rail, which conflates the ADS1115's fixed absolute input range with its PGA-dependent differential span; changing gain does not alter what the input pins tolerate.

**Clip detection.** `MAX_MUX_VOLTAGE_MV = 3000.0f` could never trigger once the voltage channel's differential span became 512 mV, so a saturated reading would have been reported at full scale with quality `OK` — silently wrong rather than merely imprecise. The `V_RANGE` guard is now tied to 98% of the PGA full scale. The 3.3 V mux constant is retained as a record of the analog rail constraint.

**Electrodes.** Iron nails are replaced by 304/316 stainless steel screws. Iron corrodes in sap within hours and its oxide layer is an unstable conductor, so contact impedance drifts continuously and differently at each of the twelve electrodes. Screws also grip more repeatably than hammered nails, making insertion depth consistent and removal non-destructive.

**Compliance ceiling — measured, no change needed.** The current path is constrained to the 3.3 V mux rail, capping drivable load at roughly 10.7 kΩ at 300 µA. Measured electrode-to-electrode resistance is about 1.5 kΩ, where up to ~1.8 mA is available: six times the required headroom. Revisit only if a trunk measures above ~9 kΩ, which would appear as `I_LOW` flags rather than a wiring fault.

## Decided, not yet implemented

- **Scan loop restructure.** `configureDriveAndSense()` zeroes the DAC and disables all four muxes for every measurement, rebuilding the injection path 216 times per frame even though the injection pair is constant across the inner voltage sweep. Each teardown collapses the electrode polarization layer, and `muxSettleMs` is then spent waiting for it to re-form. The decision is to configure injection once per injection pair (24 per frame) and hold it while the voltage muxes sweep, which should cut estimated frame time at 100 ms settle from ~40 s to ~8 s. This is the change most likely to address the elapsed-time drift above. Note that `test_switching_goes_idle_before_mux_addresses_change` currently asserts the per-measurement teardown order and will need updating with it.

## Open, pending measurement

- **Mains hum.** Sampling averages over ~11 ms, about two thirds of a 60 Hz cycle, so hum does not cancel and leaves a residue that varies per measurement. The fix is continuous mode averaging 43 samples at 860 SPS (50.0 ms, exactly 3 cycles), which is also faster than the current 16-sample setting. To be confirmed first by comparing baseline drift with the laptop on battery versus plugged in.
- **Injection current.** DAC 100 (~335 µA) uses about a sixth of the available current, and noise sources are fixed in absolute terms so more current should improve SNR. But higher current thickens the polarization layer, and above ~1.6× the peak voltage would clip `GAIN_EIGHT`. To be resolved by sweeping DAC 100/150/200/300 on the phantom and recording drift against the 5th-percentile voltage at each.

## Consequences

- Every change alters the measured numbers, so a phantom run on the current build should be kept as the before-comparison.
- `docs/drift-tuning-presets.md` results predate all of this and are not comparable to future runs.
- If frame time drops as expected, the settle and sample presets in that document need re-deriving rather than reusing.
