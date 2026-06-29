# ESP32-S3 Phase 3A Unified ERT Firmware

Arduino IDE firmware for the complete 12-electrode Phase 3A breadboard:

- four independently addressed CD74HC4067 muxes;
- MCP4725-controlled OPA2134 Improved Howland current pump;
- ADS1115 A0-A1 differential electrode voltage;
- ADS1115 A2-A3 differential voltage across a 100-ohm return shunt;
- adjacent, skip-1, skip-2, or opposite drive selected at runtime; and
- automatic forward/reverse injection records.

## Required Libraries

Install through Arduino Library Manager:

- `Adafruit ADS1X15`
- `Adafruit MCP4725`

## Critical Wiring

| Signal | Connection |
|---|---|
| MCP4725 VOUT | HCP Vp through R3 |
| HCP I_SRC_OUT | MUX_I_SRC SIG/COM |
| MUX_I_RET SIG/COM | ADS1115 A2 and top of 100-ohm shunt |
| Bottom of 100-ohm shunt | ADS1115 A3 and system GND |
| MUX_VP SIG/COM | ADS1115 A0 through 1-kohm series resistor |
| MUX_VN SIG/COM | ADS1115 A1 through 1-kohm series resistor |

Add a 10-kohm pull-up from every mux `EN` pin to 3.3 V so all muxes remain
disabled while the ESP32 boots.

## Commands

Use Serial Monitor at 115200 baud with newline enabled.

| Command | Action |
|---|---|
| `s` | capture one complete forward/reverse frame |
| `ma` | select adjacent drive |
| `ms` | select skip-1 drive |
| `mk` | select skip-2 drive |
| `mo` | select opposite drive |
| `p100` | request DAC code 100 during measurements |
| `t10` | set 10 ms settling time |
| `n4` | average four ADC conversions |
| `g` | start continuous frames |
| `x` | stop and force DAC/muxes idle |
| `i` | scan I2C bus for MCP4725 and ADS1115 |
| `?` | print status |
| `h` | print help |

The `p` command stores the requested drive level but leaves the physical DAC
at zero while idle. The firmware applies it only after all mux addresses are
set and enabled.

## Record Units

Records use millivolts for `V` and microamps for `I`:

```text
FRAME,2,1,ADJACENT,DAC,100,SETTLE,10,SAMPLES,4
M,P,FWD,I+,E1,I-,E2,V+,E3,V-,E4,V,-12.345,I,210.000,Q,OK
M,P,REV,I+,E2,I-,E1,V+,E3,V-,E4,V,12.210,I,208.500,Q,OK
END,1
```

Existing `phase3a_reconstruct.py` files parse the older voltage-only format.
They must be updated before using this v2 record format for reconstruction.

## Safety Limits

- Firmware calculates current using a 100-ohm return shunt and clips DAC commands to code 620.
- Start with `p100`.
- Never allow any CD74HC4067 analog pin or ADS1115 input outside 0-3.3 V.
- Verify I_SRC_OUT remains below 3.0 V with a multimeter before mux connection.
- `x` or reset forces a zero DAC command and disables all muxes.
