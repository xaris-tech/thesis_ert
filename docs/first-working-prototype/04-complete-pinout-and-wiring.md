# Complete Pinout and Wiring

## ESP32-S3

| ESP32 pin | Connection |
|---|---|
| `3V3` | MCP4725 VDD, ADS1115 VDD, all mux VCC pins |
| `GND` | MCP4725, ADS1115, mux grounds, analog common point |
| `GPIO8` | MCP4725 SDA and ADS1115 SDA |
| `GPIO9` | MCP4725 SCL and ADS1115 SCL |
| `GPIO4/5/6/7` | `MUX_I_SRC S0/S1/S2/S3` |
| `GPIO37` | `MUX_I_SRC EN` |
| `GPIO10/11/12/13` | `MUX_I_RET S0/S1/S2/S3` |
| `GPIO38` | `MUX_I_RET EN` |
| `GPIO15/16/17/18` | `MUX_VP S0/S1/S2/S3` |
| `GPIO39` | `MUX_VP EN` |
| `GPIO36/35/41/42` | `MUX_VN S0/S1/S2/S3` |
| `GPIO40` | `MUX_VN EN` |

All `EN` inputs are active-low. Firmware must disable all muxes before address
changes. Confirm these GPIOs exist on the exact ESP32-S3 development board.

## MCP4725

| Pin | Connection |
|---|---|
| VDD | 3.3 V |
| GND | system ground |
| SDA | GPIO8 |
| SCL | GPIO9 |
| ADDR | ground, address 0x60 |
| VOUT | verified Howland command input; never directly to an electrode |

## ADS1115

| Pin | Connection |
|---|---|
| VDD | 3.3 V |
| GND | system ground |
| SDA | GPIO8 |
| SCL | GPIO9 |
| ADDR | ground, address 0x48 |
| A0 | filtered `MUX_VP` common |
| A1 | filtered `MUX_VN` common |
| A2 | current-shunt high side |
| A3 | current-shunt low side |

## Mux Common Pins

| Mux | Common connection |
|---|---|
| `MUX_I_SRC` | verified Howland `I_SRC_OUT` |
| `MUX_I_RET` | high side of the 100 ohm return shunt |
| `MUX_VP` | ADS1115 A0 input network |
| `MUX_VN` | ADS1115 A1 input network |

## Electrode Fan-Out

Wire the same channel number on every mux to the same electrode.

| Electrode | All four mux channels |
|---|---|
| E1 | C0 |
| E2 | C1 |
| E3 | C2 |
| E4 | C3 |
| E5 | C4 |
| E6 | C5 |
| E7 | C6 |
| E8 | C7 |
| E9 | C8 |
| E10 | C9 |
| E11 | C10 |
| E12 | C11 |
| unused | C12-C15, leave disconnected |

Label every wire at both ends. Verify all 48 paths before connecting the
current source.

