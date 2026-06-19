# Parts and Power

## Core Parts

| Quantity | Part | Role |
|---:|---|---|
| 1 | ESP32-S3 development board | switching and acquisition controller |
| 1 | MCP4725 module | current-command DAC |
| 1 | ADS1115 module | differential voltage/current ADC |
| 4 | CD74HC4067 module | `I+`, `I-`, `V+`, and `V-` selection |
| 1 | OPA2134PA DIP-8 | Improved Howland current source |
| 1 | positive/negative converter | adjustable analog rails |
| 1 | regulated 12 V, at least 1 A adapter | converter input |
| 1 | 100 ohm, 0.1% metal-film resistor | current-monitor shunt |
| 12 | stainless screws or nails | tree electrodes |
| 12 | equal-length alligator leads | electrode wiring |

## Additional Parts

- TI Design 2 Howland resistors, 0.1% through-hole metal film
- selectable current-setting resistors and header jumpers
- 100 nF ceramic capacitors at every IC supply
- 10-47 uF electrolytic capacitors on both OPA2134 rails
- small series resistors and RC parts for ADS1115 inputs
- 12 V input switch and small fuse
- terminal blocks, labeled hookup wire, and breadboards
- 25 mm nylon strap, buckle, and PVC cable-trunking fixture material

## Power Wiring

| From | To | Rule |
|---|---|---|
| Laptop USB | ESP32-S3 USB | digital power and serial |
| ESP32 `3V3` | MCP4725, ADS1115, four mux `VCC` pins | never use 5 V here |
| ESP32 `GND` | module grounds | digital/common reference |
| 12 V adapter | converter `VIN/GND` | verify plug polarity first |
| Converter `V+` | OPA2134 pin 8 | adjust to about +9 V |
| Converter `V-` | OPA2134 pin 4 | adjust to about -9 V |
| Converter center `GND` | controlled system-ground point | only common reference |

## Converter Qualification

Before attaching the OPA2134:

1. Measure adapter voltage and polarity.
2. Adjust `V+` to about `+9.0 V` relative to center ground.
3. Confirm `V-` is about `-9.0 V` relative to center ground.
4. Confirm `V+` to `V-` is about `18.0 V`.
5. Run for ten minutes and recheck both rails.
6. Reject the module if either output is unstable, asymmetric beyond useful
   adjustment, or becomes hot with no load.

Switching-converter noise is acceptable for initial DC ERT only after baseline
stability tests pass. Portable power is a later revision.

