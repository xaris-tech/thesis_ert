# Safety and Troubleshooting

## Non-Negotiable Rules

- Never connect this experimental instrument to a person or animal.
- Power off before changing breadboard wiring.
- Verify every rail with a multimeter before inserting an IC.
- Never connect `-9 V` to ESP32 `GND`, `3V3`, GPIO, ADC, DAC, or mux pins.
- The converter center ground, not its negative output, is system ground.
- Keep every CD74HC4067 analog terminal and ADS1115 input inside 0-3.3 V.
- Begin with the lowest current range.
- Disable current and all muxes whenever firmware is idle or disconnected.
- Add a fuse and accessible analog-power switch.

## Fault Isolation

| Symptom | First checks |
|---|---|
| current changes strongly with load | Howland resistor matching, wiring, OPA saturation |
| current slowly rises or falls | rail drift, converter heating, electrode polarization |
| values jump after switching | settle delay, break-before-make sequence, loose contacts |
| one electrode always differs | channel mapping, lead length, insertion depth, corrosion |
| ADS1115 saturates | gain, common-mode voltage, excess current, wrong grounding |
| adjacent script reports missing pairs | firmware mode/protocol mismatch |
| reconstruction rotates or mirrors | E1 orientation or clockwise numbering mismatch |
| image changes with no target | warm-up, contact motion, salinity/temperature, power noise |

## Stop Conditions

Immediately remove analog power if:

- any mux or ADC node is below ground or above 3.3 V;
- the OPA2134, converter, shunt, or mux becomes hot;
- output current exceeds the selected validated range;
- a rail changes substantially under load; or
- wiring cannot be reconciled with the pinout table.

## Interpretation Discipline

Color represents the solver's estimated relative conductivity/resistivity
change, not wood species, cavity size, or disease by itself. Always inspect
raw voltage, measured current, drift, and quality flags before interpreting a
reconstruction.

