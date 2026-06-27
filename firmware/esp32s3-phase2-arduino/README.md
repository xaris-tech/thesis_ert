# ESP32-S3 Phase 2 Firmware for Arduino IDE

This is the Arduino IDE version of the 8-electrode Phase 2 scanner firmware.

## Install First

In Arduino IDE, install these libraries with Library Manager:

- `Adafruit ADS1X15`
- `Adafruit MCP4725`

Also make sure the `ESP32` board package is installed.

## Board Setup

Use:

- Board: `ESP32S3 Dev Module` or your matching ESP32-S3 board
- Upload speed: default is fine
- Serial monitor baud: `115200`

## Sketch

Open:

- [esp32s3_phase2.ino](C:/Users/Vidad/Documents/ERT/firmware/esp32s3-phase2-arduino/esp32s3_phase2.ino)

## Pin Map

- `GPIO8`  -> I2C SDA
- `GPIO9`  -> I2C SCL
- `GPIO4`  -> `CD74HC4067 S0`
- `GPIO5`  -> `CD74HC4067 S1`
- `GPIO6`  -> `CD74HC4067 S2`
- `GPIO7`  -> `CD74HC4067 S3`
- `GPIO15` -> `CD74HC4067 EN`

## Wiring Assumptions

- `MCP4725` at `0x60`
- `ADS1115` at `0x48`
- `CD74HC4067 SIG` -> `ADS1115 A0`
- `ADS1115 A1` -> `E5`
- `LM358 / Rs node` -> `E1`
- `E5` -> current return / ground
- `CD74HC4067 C0..C7` -> `E1..E8`

## Serial Commands

- `s` single scan
- `g` continuous scanning on
- `x` continuous scanning off
- `p<number>` set DAC raw value from `0` to `4095`
- `t<number>` set mux settle time in ms
- `r<number>` set continuous scan period in ms
- `h` print help

Examples:

```text
s
p650
t10
r200
g
x
```

## Output Format

The sketch prints frames like:

```text
SCAN:
0,E1,123.456
1,E2,120.987
2,E3,118.200
3,E4,119.600
4,E5,0.000
5,E6,126.400
6,E7,129.800
7,E8,131.100
END
```

This matches the parser in [ert.py](C:/Users/Vidad/Documents/ERT/ert.py).
