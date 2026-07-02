# Drift Tuning Presets

Use this file to track which UI tuning presets were tried and what happened.

## Goal

Reduce same-condition drift before trusting target reconstruction.

Good direction:

- `max_relative` lower is better.
- `max_rms` lower is better.
- `min_corr` closer to `1.0` is better.

Current baseline gate:

- Relative RMS must be `<= 2.00%`.
- Absolute RMS must be `<= 0.002000 kOhm`.
- Minimum correlation must be `>= 0.99500`.

## Previous Presets And Results

These came from the July 2 UI log.

| Attempt | Settle ms | Samples | Warmup | Baseline | Control frames | Result |
|---|---:|---:|---:|---:|---:|---|
| 1 | 30 | 4 | 10 | 10 | 20 | Failed baseline: relative `26.99%`, absolute `0.003853 kOhm`, correlation `0.96406` |
| 2 | 50 | 8 | 10 | 10 | 10 | Failed baseline: relative `94.70%`, absolute `0.018270 kOhm`, correlation `0.70349` |
| 3 | 100 | 16 | 10 | 10 | 10 | Failed baseline: relative `9.20%`, absolute `0.002895 kOhm`, correlation `0.99605` |
| 4 | 200 | 16 | 10 | 15 | 15 | Failed baseline: relative `18.60%`, absolute `0.006399 kOhm`, correlation `0.98389` |

Best previous direction:

- `100ms / 16 samples` had the best correlation and lowest relative drift.
- It still failed relative and absolute baseline stability.
- New presets focus around this setting with longer warmup and more baseline frames.

## Current UI Tune Drift Presets

The UI now tries the current settings first, then these targeted presets.

| Preset | Settle ms | Samples | Warmup | Baseline | Control frames | Reason |
|---|---:|---:|---:|---:|---:|---|
| Current | UI value | UI value | UI value | UI value | UI value | Keeps a direct comparison to your manual settings |
| A | 100 | 16 | 20 | 10 | 10 | Same best direction, more time to settle before baseline |
| B | 100 | 16 | 30 | 15 | 10 | Same signal settings, more warmup and stronger baseline average |
| C | 150 | 16 | 30 | 20 | 10 | Slightly slower settling, stronger baseline average |
| D | 200 | 32 | 30 | 20 | 10 | Slowest/cleanest debug profile; checks if noise is sample-limited |

## Results Log

Copy new `Tune attempt` results here.

| Date | Setup notes | Preset | Settle ms | Samples | Warmup | Baseline | Control frames | Result |
|---|---|---|---:|---:|---:|---:|---:|---|
| 2026-07-02 | Initial UI tune run | Old 1 | 30 | 4 | 10 | 10 | 20 | Failed baseline: relative `26.99%`, absolute `0.003853 kOhm`, correlation `0.96406` |
| 2026-07-02 | Initial UI tune run | Old 2 | 50 | 8 | 10 | 10 | 10 | Failed baseline: relative `94.70%`, absolute `0.018270 kOhm`, correlation `0.70349` |
| 2026-07-02 | Initial UI tune run | Old 3 | 100 | 16 | 10 | 10 | 10 | Failed baseline: relative `9.20%`, absolute `0.002895 kOhm`, correlation `0.99605` |
| 2026-07-02 | Initial UI tune run | Old 4 | 200 | 16 | 10 | 15 | 15 | Failed baseline: relative `18.60%`, absolute `0.006399 kOhm`, correlation `0.98389` |

## Notes While Testing

- Close any other serial monitor or old UI window before connecting to `COM3`.
- Do not move electrodes, wires, water, or the tree during baseline/tune.
- If `100ms / 16 samples` improves again but still fails absolute drift, check contact quality before increasing only software averaging.
- If longer warmup helps, the setup likely needs physical settling time.
- If higher samples helps, random ADC/current noise is likely part of the issue.
