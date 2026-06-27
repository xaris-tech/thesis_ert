# Phase 3A Pinout Tables

This document is only for concrete wiring/pinout planning.

Target build:

- ERT, not impedance spectroscopy
- `12` electrodes
- breadboard-first
- `ESP32-S3`
- `MCP4725`
- `ADS1115`
- `CD74HC4067 x4`
- improved current pump replacing `LM358`

## Important Control Note

For real reconstruction, each mux must be able to select a different electrode.

That means each mux needs independent address control:

- `MUX_I_SRC` selects current source electrode
- `MUX_I_RET` selects current return electrode
- `MUX_VP` selects voltage positive electrode
- `MUX_VN` selects voltage negative electrode

If all muxes share the same `S0..S3`, they all point to the same electrode. That is not enough for full reconstruction.

## ESP32-S3

| ESP32-S3 Pin | Connects To | Purpose |
|---|---|---|
| `3V3` | `MCP4725 VDD`, `ADS1115 VDD`, all `CD74HC4067 VCC` | logic/module power |
| `GND` | all module grounds | common ground |
| `GPIO8` | `MCP4725 SDA`, `ADS1115 SDA` | I2C data |
| `GPIO9` | `MCP4725 SCL`, `ADS1115 SCL` | I2C clock |
| `GPIO4` | `MUX_I_SRC S0` | source mux address bit 0 |
| `GPIO5` | `MUX_I_SRC S1` | source mux address bit 1 |
| `GPIO6` | `MUX_I_SRC S2` | source mux address bit 2 |
| `GPIO7` | `MUX_I_SRC S3` | source mux address bit 3 |
| `GPIO10` | `MUX_I_RET S0` | return mux address bit 0 |
| `GPIO11` | `MUX_I_RET S1` | return mux address bit 1 |
| `GPIO12` | `MUX_I_RET S2` | return mux address bit 2 |
| `GPIO13` | `MUX_I_RET S3` | return mux address bit 3 |
| `GPIO15` | `MUX_VP S0` | voltage positive mux address bit 0 |
| `GPIO16` | `MUX_VP S1` | voltage positive mux address bit 1 |
| `GPIO17` | `MUX_VP S2` | voltage positive mux address bit 2 |
| `GPIO18` | `MUX_VP S3` | voltage positive mux address bit 3 |
| `GPIO36` | `MUX_VN S0` | voltage negative mux address bit 0 |
| `GPIO35` | `MUX_VN S1` | voltage negative mux address bit 1 |
| `GPIO41` | `MUX_VN S2` | voltage negative mux address bit 2 |
| `GPIO42` | `MUX_VN S3` | voltage negative mux address bit 3 |
| `GPIO37` | `MUX_I_SRC EN` | active-low enable |
| `GPIO38` | `MUX_I_RET EN` | active-low enable |
| `GPIO39` | `MUX_VP EN` | active-low enable |
| `GPIO40` | `MUX_VN EN` | active-low enable |

Note: do not reuse `GPIO15` on both `MUX_VP` and `MUX_VN`. Also avoid `GPIO0` for mux address lines because it can affect boot behavior on ESP32-S3 boards.

## MCP4725

| MCP4725 Pin | Connects To | Purpose |
|---|---|---|
| `VDD` | `ESP32-S3 3V3` | DAC supply |
| `GND` | `GND` | common ground |
| `SDA` | `ESP32-S3 GPIO8` | I2C data |
| `SCL` | `ESP32-S3 GPIO9` | I2C clock |
| `ADDR` | `GND` | address `0x60` |
| `VOUT` | current pump setpoint input | controls commanded current |

## ADS1115

| ADS1115 Pin | Connects To | Purpose |
|---|---|---|
| `VDD` | `ESP32-S3 3V3` | ADC supply |
| `GND` | `GND` | common ground |
| `SDA` | `ESP32-S3 GPIO8` | I2C data |
| `SCL` | `ESP32-S3 GPIO9` | I2C clock |
| `ADDR` | `GND` | address `0x48` |
| `A0` | `MUX_VP SIG/COM` | differential voltage positive |
| `A1` | `MUX_VN SIG/COM` | differential voltage negative |
| `A2` | optional `ISENSE_P` later | leave open for first build |
| `A3` | optional `ISENSE_N` later | leave open for first build |

## Current Pump Op Amp

Use `OPA2134PA`, `OPA2277PA`, or temporary `LM358` for early switching tests.

Standard dual op amp DIP pinout:

| DIP Pin | Op Amp Node | Connects To | Purpose |
|---:|---|---|---|
| `1` | `OUT A` | HCP output network | current pump output drive |
| `2` | `IN- A` | HCP negative feedback node | feedback |
| `3` | `IN+ A` | HCP positive input network | DAC/setpoint side |
| `4` | `V-` | `GND` for single-supply test or `-AVDD` later | negative supply |
| `5` | `IN+ B` | `GND` or mid-supply reference | unused op amp tie-off |
| `6` | `IN- B` | pin `7` | unused follower tie-off |
| `7` | `OUT B` | pin `6` | unused follower tie-off |
| `8` | `V+` | `+5V`, `+9V`, `+12V`, or `+AVDD` depending on test | positive supply |

## MUX_I_SRC: CD74HC4067

| CD74HC4067 Pin | Connects To | Purpose |
|---|---|---|
| `VCC` | `ESP32-S3 3V3` | mux supply |
| `GND` | `GND` | common ground |
| `EN` | `ESP32-S3 GPIO37` | active-low enable |
| `S0` | `ESP32-S3 GPIO4` | address bit 0 |
| `S1` | `ESP32-S3 GPIO5` | address bit 1 |
| `S2` | `ESP32-S3 GPIO6` | address bit 2 |
| `S3` | `ESP32-S3 GPIO7` | address bit 3 |
| `SIG/COM` | `I_SRC_OUT` | source current common |
| `C0` | `E1` | electrode 1 |
| `C1` | `E2` | electrode 2 |
| `C2` | `E3` | electrode 3 |
| `C3` | `E4` | electrode 4 |
| `C4` | `E5` | electrode 5 |
| `C5` | `E6` | electrode 6 |
| `C6` | `E7` | electrode 7 |
| `C7` | `E8` | electrode 8 |
| `C8` | `E9` | electrode 9 |
| `C9` | `E10` | electrode 10 |
| `C10` | `E11` | electrode 11 |
| `C11` | `E12` | electrode 12 |
| `C12-C15` | no connect | unused |

## MUX_I_RET: CD74HC4067

| CD74HC4067 Pin | Connects To | Purpose |
|---|---|---|
| `VCC` | `ESP32-S3 3V3` | mux supply |
| `GND` | `GND` | common ground |
| `EN` | `ESP32-S3 GPIO38` | active-low enable |
| `S0` | `ESP32-S3 GPIO10` | address bit 0 |
| `S1` | `ESP32-S3 GPIO11` | address bit 1 |
| `S2` | `ESP32-S3 GPIO12` | address bit 2 |
| `S3` | `ESP32-S3 GPIO13` | address bit 3 |
| `SIG/COM` | `I_RET_OUT` | return current common |
| `C0` | `E1` | electrode 1 |
| `C1` | `E2` | electrode 2 |
| `C2` | `E3` | electrode 3 |
| `C3` | `E4` | electrode 4 |
| `C4` | `E5` | electrode 5 |
| `C5` | `E6` | electrode 6 |
| `C6` | `E7` | electrode 7 |
| `C7` | `E8` | electrode 8 |
| `C8` | `E9` | electrode 9 |
| `C9` | `E10` | electrode 10 |
| `C10` | `E11` | electrode 11 |
| `C11` | `E12` | electrode 12 |
| `C12-C15` | no connect | unused |

## MUX_VP: CD74HC4067

| CD74HC4067 Pin | Connects To | Purpose |
|---|---|---|
| `VCC` | `ESP32-S3 3V3` | mux supply |
| `GND` | `GND` | common ground |
| `EN` | `ESP32-S3 GPIO39` | active-low enable |
| `S0` | `ESP32-S3 GPIO15` | address bit 0 |
| `S1` | `ESP32-S3 GPIO16` | address bit 1 |
| `S2` | `ESP32-S3 GPIO17` | address bit 2 |
| `S3` | `ESP32-S3 GPIO18` | address bit 3 |
| `SIG/COM` | `ADS1115 A0` | voltage positive common |
| `C0` | `E1` | electrode 1 |
| `C1` | `E2` | electrode 2 |
| `C2` | `E3` | electrode 3 |
| `C3` | `E4` | electrode 4 |
| `C4` | `E5` | electrode 5 |
| `C5` | `E6` | electrode 6 |
| `C6` | `E7` | electrode 7 |
| `C7` | `E8` | electrode 8 |
| `C8` | `E9` | electrode 9 |
| `C9` | `E10` | electrode 10 |
| `C10` | `E11` | electrode 11 |
| `C11` | `E12` | electrode 12 |
| `C12-C15` | no connect | unused |

## MUX_VN: CD74HC4067

| CD74HC4067 Pin | Connects To | Purpose |
|---|---|---|
| `VCC` | `ESP32-S3 3V3` | mux supply |
| `GND` | `GND` | common ground |
| `EN` | `ESP32-S3 GPIO40` | active-low enable |
| `S0` | `ESP32-S3 GPIO36` | address bit 0 |
| `S1` | `ESP32-S3 GPIO35` | address bit 1 |
| `S2` | `ESP32-S3 GPIO41` | address bit 2 |
| `S3` | `ESP32-S3 GPIO42` | address bit 3 |
| `SIG/COM` | `ADS1115 A1` | voltage negative common |
| `C0` | `E1` | electrode 1 |
| `C1` | `E2` | electrode 2 |
| `C2` | `E3` | electrode 3 |
| `C3` | `E4` | electrode 4 |
| `C4` | `E5` | electrode 5 |
| `C5` | `E6` | electrode 6 |
| `C6` | `E7` | electrode 7 |
| `C7` | `E8` | electrode 8 |
| `C8` | `E9` | electrode 9 |
| `C9` | `E10` | electrode 10 |
| `C10` | `E11` | electrode 11 |
| `C11` | `E12` | electrode 12 |
| `C12-C15` | no connect | unused |

## Electrode Connector

| Connector Pin | Connects To | Notes |
|---:|---|---|
| `1` | `E1` | electrode 1 |
| `2` | `E2` | electrode 2 |
| `3` | `E3` | electrode 3 |
| `4` | `E4` | electrode 4 |
| `5` | `E5` | electrode 5 |
| `6` | `E6` | electrode 6 |
| `7` | `E7` | electrode 7 |
| `8` | `E8` | electrode 8 |
| `9` | `E9` | electrode 9 |
| `10` | `E10` | electrode 10 |
| `11` | `E11` | electrode 11 |
| `12` | `E12` | electrode 12 |
