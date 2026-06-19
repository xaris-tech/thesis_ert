# Windows App and Reconstruction

## Technology

Use Python, Tkinter, pyserial, NumPy, Matplotlib, and PyEIT. Keep acquisition,
protocol parsing, quality analysis, storage, and reconstruction in separate
modules so each can be tested without hardware.

## Main Screen

- serial port and connection status
- firmware/protocol version
- adjacent/opposite selector
- current range and DAC command
- settle time, samples, and frame-average count
- experiment metadata form
- baseline capture button
- anomaly capture button
- stop/emergency idle button
- live current, voltage, drift, and quality indicators
- reconstruction plot with E1-E12 labels and E1 orientation

## Experiment Metadata

Require:

- experiment and sample ID
- saline, banana, cut trunk, or living tree
- species when known
- circumference and scan height
- electrode type, insertion depth, and E1 orientation
- pattern, current range, DAC code, settling, and averaging
- baseline/anomaly description and notes

## Data Processing

Preserve raw forward/reverse records. Pair them by the physical injection and
measurement combination, correct polarity, and calculate approximately:

```text
V_corrected = (V_forward - mapped_V_reverse) / 2
I_magnitude = robust mean of measured forward/reverse current magnitude
transfer_resistance = V_corrected / I_magnitude
```

Reject records with saturation, missing pairs, insufficient current, large
forward/reverse disagreement, or mux/firmware errors.

## Reconstruction

- build a protocol-specific PyEIT measurement ordering;
- require identical baseline/anomaly configuration;
- average stable frames before inversion;
- reconstruct relative conductivity/resistivity change;
- display electrode numbers and orientation;
- show a fixed, symmetric color scale when comparing runs; and
- label results experimental and relative.

## Storage

Each run gets a timestamped folder containing metadata JSON, raw CSV, processed
NumPy arrays, quality summary, reconstruction settings, and PNG output. Never
discard raw data when processing rules change.

