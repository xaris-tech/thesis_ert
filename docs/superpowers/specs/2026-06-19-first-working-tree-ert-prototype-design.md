# First Working Tree-ERT Prototype Design

## Objective

Build a bench-powered, Windows-laptop-operated, 12-electrode DC ERT prototype
that localizes controlled conductivity anomalies in a saline tank, banana
pseudostem, and sacrificial tree-trunk samples.

## Approved Architecture

- ESP32-S3 with MCP4725, ADS1115, and four independently controlled
  CD74HC4067 muxes
- OPA2134PA buffered TI Design 2 Improved Howland current source
- selectable approximately 100 uA, 500 uA, and 1 mA current ranges
- ADS1115 differential boundary-voltage and return-shunt measurements
- selectable adjacent and opposite drive patterns in one firmware
- paired forward/reverse DC injection to reduce static electrode offsets
- Windows Tkinter application for control, metadata, logging, quality checks,
  and PyEIT difference reconstruction
- adjustable 12-electrode tree strap and rigid 12-electrode saline tank

## Validation Strategy

Use pass/fail stage gates for power, current source, current monitor, ADC, mux
matrix, integrated dummy loads, saline tank, banana pseudostem, and cut trunk.
The first scientific claim is relative anomaly localization, not absolute
single-scan tree diagnosis.

## Detailed Design

The complete approved design is split into the files under
`docs/first-working-prototype/`, beginning with its `README.md`. Those files
are normative for Prototype 1 and supersede older Phase 2 wiring assumptions.

