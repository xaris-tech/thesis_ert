# First Working Tree-ERT Prototype

This folder defines the first complete 12-electrode DC Electrical Resistance
Tomography prototype for saline-tank and tree-sample experiments.

## Intended Result

The instrument must:

- inject controlled, polarity-reversed DC through 12 boundary electrodes;
- support adjacent and opposite drive patterns without reflashing firmware;
- measure boundary voltage and actual injected current;
- save traceable baseline and anomaly datasets on a Windows laptop; and
- reconstruct a relative conductivity/resistivity-change map with PyEIT.

It is an experimental anomaly-localization instrument, not a camera or a
validated tree-decay diagnostic device.

## Build Order

1. [Scope and acceptance criteria](00-project-scope.md)
2. [System architecture](01-system-architecture.md)
3. [Parts and power](02-parts-and-power.md)
4. [Improved Howland current source](03-howland-current-source.md)
5. [Complete pinout and wiring](04-complete-pinout-and-wiring.md)
6. [Electrode fixtures](05-electrode-fixtures.md)
7. [Firmware and serial protocol](06-firmware-and-serial-protocol.md)
8. [Windows app and reconstruction](07-windows-app-and-reconstruction.md)
9. [Bring-up and testing](08-bring-up-and-testing.md)
10. [Saline and tree experiments](09-saline-and-tree-experiments.md)
11. [Safety and troubleshooting](10-safety-and-troubleshooting.md)

Do not skip directly to the tree experiment. Each stage has pass/fail checks
that isolate faults before the complete system is connected.

