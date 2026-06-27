# ESP32-S3 Phase 3A ERT Firmware

Arduino IDE firmware for the 12-electrode breadboard ERT scanner.

## Libraries

Install in Arduino IDE:

- `Adafruit ADS1X15`
- `Adafruit MCP4725`

## Pin Map

Use the pinout in [PHASE_3A_PINOUT_TABLES.md](C:/Users/Vidad/Documents/ERT/PHASE_3A_PINOUT_TABLES.md).

Important correction:

- `MUX_VP S0..S3` = `GPIO15`, `GPIO16`, `GPIO17`, `GPIO18`
- `MUX_VN S0..S3` = `GPIO36`, `GPIO35`, `GPIO41`, `GPIO42`
- avoid `GPIO0`
- do not share `GPIO15` between muxes

## Commands

- `h` help
- `s` single full ERT frame
- `o` single opposite-drive ERT frame
- `g` continuous frames
- `x` stop continuous frames
- `p<number>` set MCP4725 DAC raw code
- `t<number>` set mux settle time in ms
- `r<number>` set continuous frame period in ms

## Output

The firmware emits full frame records:

```text
FRAME:
I+,E1,I-,E2,V+,E4,V-,E5,V,-12.345
...
END
```
