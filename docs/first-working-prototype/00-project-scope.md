# Project Scope

## Prototype 1 Goal

Build a bench-powered, laptop-operated, 12-electrode DC ERT instrument that
can localize a controlled conductivity anomaly in:

1. a circular saline tank;
2. a banana pseudostem;
3. a sacrificial tree-trunk sample; and
4. later, a living tree for repeatability studies.

## Reconstruction Meaning

The output is a relative conductivity/resistivity-change map. It compares an
intact baseline with a second scan after introducing a known cavity, wet
region, dry region, or target. It is not a literal image of internal anatomy.

## Required Features

- 12 electrodes in one cross-sectional plane
- independently switched `I+`, `I-`, `V+`, and `V-`
- selectable adjacent and opposite current-drive patterns
- forward and reverse DC measurements for each injection pair
- actual-current measurement and `V/I` normalization
- automated metadata and raw-data logging
- PyEIT difference reconstruction
- visible quality checks before reconstruction

## Deferred Features

- battery or power-bank operation
- enclosure and handheld packaging
- absolute single-scan diagnosis of an unknown tree
- 16-electrode expansion
- custom PCB
- clinical, human, or animal use

## Acceptance Criteria

- all power rails and analog nodes remain inside component ratings;
- current varies by no more than about 5% across the validated dummy-load range;
- firmware produces complete, correctly ordered frames with no invalid pairs;
- stationary baseline drift is materially smaller than the controlled target response;
- repeated reconstructions place a known anomaly in the correct sector; and
- experiment folders contain enough metadata and raw data to reproduce results.

