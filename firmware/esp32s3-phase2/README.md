# ESP32-S3 Phase 2 Firmware

This firmware targets an `ESP32-S3 DevKitC-1` using the Arduino framework in PlatformIO.

## Purpose

It scans an 8-electrode ring with:

- fixed current injection in hardware: `E1` drive, `E5` return
- voltage sensing through one `CD74HC4067`
- differential ADC reading with `ADS1115 A0-A1`
- DAC drive setpoint from `MCP4725`

The serial output is compatible with the Python tool in [ert.py](C:/Users/Vidad/Documents/ERT/ert.py):

```text
SCAN:
0,E1,123.456
1,E2,120.987
...
7,E8,131.250
END
```

## Pin Map

- `GPIO8`  -> I2C SDA
- `GPIO9`  -> I2C SCL
- `GPIO4`  -> CD74HC4067 `S0`
- `GPIO5`  -> CD74HC4067 `S1`
- `GPIO6`  -> CD74HC4067 `S2`
- `GPIO7`  -> CD74HC4067 `S3`
- `GPIO15` -> CD74HC4067 `EN` (active low)

## Wiring Assumptions

- `MCP4725` at address `0x60`
- `ADS1115` at address `0x48`
- `CD74HC4067 SIG` connected to `ADS1115 A0`
- `ADS1115 A1` connected to `E5`
- `LM358 / Rs injection node` connected to `E1`
- `E5` connected to current return / ground
- `CD74HC4067 C0..C7` connected to `E1..E8`

## Commands

- `s` single scan
- `g` enable continuous scanning
- `x` disable continuous scanning
- `p<number>` set DAC raw value from `0` to `4095`
- `t<number>` set mux settle time in milliseconds
- `r<number>` set continuous scan period in milliseconds
- `h` print help/status

Examples:

```text
s
p650
t10
r200
g
x
```

## Flashing

Install PlatformIO first, then from this folder run:

```powershell
pio run
pio run -t upload
pio device monitor -b 115200
```

If your board uses a different upload port:

```powershell
pio run -t upload --upload-port COM3
pio device monitor -b 115200 --port COM3
```
