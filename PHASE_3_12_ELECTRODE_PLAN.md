# Phase 3 Plan: 12-Electrode Reconstruction Hardware for ERT

## Breadboard-First Version

This doc assumes:

- student build
- breadboard first
- reuse as much current hardware as possible
- final ERT reconstruction still goal

Meaning:

- keep architecture realistic
- do not overbuild too early
- split work into:
  - `Phase 3A` = breadboard proof
  - `Phase 3B` = cleaner final build

## Goal

Build first real reconstruction-capable version of this project for **ERT**.

Target:

- `12` electrodes
- circular boundary geometry
- switched current injection pair
- switched differential voltage measurement pair
- data quality high enough for `PyEIT`-style **ERT difference reconstruction**

This file is schematic-planning guide.

## Short Answer First

### ERT focus

This plan is for:

- **ERT** = Electrical Resistance Tomography

Not for:

- strict high-performance AC impedance system

Meaning:

- resistive / low-frequency measurements acceptable
- `ADS1115` can stay longer
- breadboard-first approach acceptable
- noise still matters, but no need overbuild too early

### Is `12` electrodes good enough?

Yes.

`12` electrodes good enough for real working reconstruction prototype.

It is not as strong as `16`, but much easier to finish in hardware.

Recommendation:

- use `12` electrodes for Phase 3
- get real ERT reconstruction working
- only move to `16` later if image quality needs improvement

## Why Phase 2 Not Enough

Current Phase 2 setup has:

- fixed injection pair
- one sensing mux
- limited measurements per frame

That is enough for:

- scanning
- drift analysis
- field-response experiments

That is **not** enough for:

- proper ERT inverse solve
- proper `PyEIT` reconstruction input

Phase 3 must add:

- current source upgrade
- switched `I+`
- switched `I-`
- switched `V+`
- switched `V-`
- better measurement architecture
- circular 12-electrode geometry

## Recommended Phase 3 Architecture

### Final hardware blocks

1. `ESP32-S3`
2. DAC for current setpoint
3. better op amp current source replacing `LM358`
4. switch matrix for `I+`, `I-`, `V+`, `V-`
5. ADC for voltage sensing and optional current monitor
6. circular 12-electrode phantom / tank
7. clean analog and digital power rails

### Breadboard-first recommendation

For first breadboard reconstruction prototype, use:

1. `ESP32-S3`
2. `MCP4725`
3. improved current source replacing `LM358`
4. multiple `CD74HC4067` switch paths
5. keep `ADS1115` first
6. `12` electrodes in circular geometry

Later, for cleaner final version:

1. move off breadboard
2. replace `ADS1115` only if needed
3. tighten analog layout

## Recommended Parts

| Block | Breadboard-first part | Final-upgrade part | Quantity | Why |
|---|---|---|---:|---|
| MCU | `ESP32-S3` | `ESP32-S3` | 1 | already used, enough control + comms |
| Current-source op amp | `OPA2197` | `OPA2197` | 1 | precision RRIO, much better than `LM358` |
| DAC | `MCP4725` | `MCP4725` | 1 | reuse existing part |
| Injection/source switch | `CD74HC4067` | `CD74HC4067` or `ADG1606` | 1 | reuse first, upgrade later if needed |
| Injection/return switch | `CD74HC4067` | `CD74HC4067` or `ADG1606` | 1 | same |
| Voltage sense positive switch | `CD74HC4067` | `CD74HC4067` or `ADG1606` | 1 | same |
| Voltage sense negative switch | `CD74HC4067` | `CD74HC4067` or `ADG1606` | 1 | same |
| ADC | `ADS1115` | `ADS1115` or `ADS131M04` | 1 | `ADS1115` acceptable longer for ERT |
| Split-rail analog supply | optional in 3A | `TPS65131` | 1 | cleaner final analog stage later |

## Key Part Decisions

### 1. MCU

- `ESP32-S3`

Why:

- already used in project
- enough GPIO / SPI / I2C
- enough compute for scan sequencing and data streaming

### 2. LM358 replacement

- **Breadboard budget choice:** `OPA2134PA`
- **Breadboard precision choice:** `OPA2277PA`
- **Cleaner later choice:** `OPA2197` on adapter/PCB

Why these are better than `LM358`:

- lower offset / drift than `LM358`
- better analog behavior
- available in `PDIP-8` breadboard-friendly packages for `OPA2134PA` and `OPA2277PA`
- practical for student breadboard build

Short answer:

- yes, replace `LM358`
- use `OPA2134PA` if cost matters most
- use `OPA2277PA` if precision matters more

### 3. Current source topology

- **Recommended:** improved Howland current pump using one half of the dual op amp

Why:

- TI supports this topology for `OPA197` family
- good for voltage-controlled current source design
- much better than present simple LM358 stage

## Improved Howland Current Pump Pinout

This section is for the breadboard version using `OPA2134PA` or `OPA2277PA`.

Both are standard dual op amp `PDIP-8` parts.

### Dual op amp DIP pinout

Top view, notch up:

```text
        _________
OUT A  |1      8| V+
IN- A  |2      7| OUT B
IN+ A  |3      6| IN- B
V-     |4      5| IN+ B
        ---------
```

### Use op amp A for the HCP

| DIP Pin | Op Amp Node | Connect To | Purpose |
|---:|---|---|---|
| `1` | `OUT A` | `HCP_OPAMP_OUT` | drives Howland resistor network |
| `2` | `IN- A` | `HCP_IN_NEG` | negative input feedback node |
| `3` | `IN+ A` | `HCP_IN_POS` | positive input / DAC reference network |
| `4` | `V-` | `AGND` for single-supply test, or `-AVDD` for split supply | negative supply |
| `8` | `V+` | `+5V` or `+AVDD` | positive supply |

### Unused op amp B

Do not leave op amp B floating.

| DIP Pin | Op Amp Node | Connect To | Purpose |
|---:|---|---|---|
| `5` | `IN+ B` | `AGND` or mid-supply reference | stable unused input |
| `6` | `IN- B` | `OUT B` / pin `7` | voltage follower tie-off |
| `7` | `OUT B` | `IN- B` / pin `6` | voltage follower tie-off |

### HCP named resistor connections

Use matched resistors where possible.

| Part | Connect From | Connect To | Notes |
|---|---|---|---|
| `R1` | `MCP4725 VOUT` | `HCP_IN_POS` | DAC command path |
| `R2` | `HCP_IN_POS` | `AGND` or reference node | positive-side ratio resistor |
| `R3` | `HCP_OPAMP_OUT` | `HCP_IN_NEG` | feedback resistor |
| `R4` | `HCP_IN_NEG` | `I_SRC_OUT` | load/output sense resistor |
| `Rsense` | `I_RET_OUT` | `AGND` or return node | optional current monitor |

### External connection summary

| HCP Net | Connects To | Notes |
|---|---|---|
| `MCP4725 VOUT` | `R1` | controls commanded current |
| `HCP_OPAMP_OUT` | `R3` and Howland output network | not directly to electrode mux |
| `I_SRC_OUT` | common pin of `MUX_I_SRC` | selected electrode receives source current |
| `I_RET_OUT` | common pin of `MUX_I_RET` | selected return electrode |
| `V_SENSE_P` | common pin of `MUX_VP` | voltage measurement positive |
| `V_SENSE_N` | common pin of `MUX_VN` | voltage measurement negative |

### Breadboard note

Start with single-supply testing if it is simpler, but expect less voltage headroom.

For cleaner current drive, use split supply later.

### 4. Analog switches

- **Breadboard-first:** `CD74HC4067 x4`
- **Cleaner final upgrade:** `ADG1606 x4`

Use:

- `1x` switch for `I+`
- `1x` switch for `I-`
- `1x` switch for `V+`
- `1x` switch for `V-`

Why `CD74HC4067` still okay here:

- cheap
- familiar
- easy to source
- good enough for student breadboard ERT proof

### 5. ADC

- **Breadboard-first:** keep `ADS1115`
- **Final upgrade only if needed:** `ADS131M04`

Why keep `ADS1115` first:

- already owned
- easy breakout/module
- easier breadboard wiring
- acceptable for student ERT prototype
- lets you prove switching architecture first

Why upgrade later only if needed:

- `ADS1115` slower
- lower resolution
- not simultaneous
- may become limiting later, but not first blocker

Use `ADS1115` in `Phase 3A` to prove:

- switched injection works
- switched sensing works
- full measurement frames can be collected
- first ERT reconstruction can be attempted

### 6. Dual-rail analog supply

- **Breadboard-first:** optional
- **Final upgrade:** `TPS65131`

Why:

- cleaner analog headroom
- better for final current source stage

### 7. DAC

- keep `MCP4725`

Why:

- already known in project
- enough if current setpoint changes slowly

## Official Source Notes

These recommendations based on vendor docs:

- `OPA2197`: dual precision RRIO op amp  
  Source: [TI OPA2197](https://www.ti.com/product/OPA2197)
- improved Howland current pump reference for `OPA197` family  
  Source: [TI CIRCUIT060044 Improved Howland Current Pump](https://www.ti.com/tool/CIRCUIT060044)
- `ADS131M04`: simultaneous `4`-channel, `24-bit` ADC  
  Source: [TI ADS131M04](https://www.ti.com/product/ADS131M04)
- `TPS65131`: split-rail converter  
  Source: [TI TPS65131](https://www.ti.com/product/TPS65131)

## Electrode Geometry

### Final Phase 3 geometry

- `12` electrodes
- evenly spaced
- circular or near-circular boundary

Do **not** use line geometry for reconstruction.

Line geometry fine for debugging only.

For real reconstruction:

- equal spacing matters
- stable contact area matters
- circular boundary matters

## Full Electrode Naming

Use:

- `E1`
- `E2`
- `E3`
- `E4`
- `E5`
- `E6`
- `E7`
- `E8`
- `E9`
- `E10`
- `E11`
- `E12`

## Top-Level Signal Names

Use these nets in schematic:

- `I_SRC_OUT`
- `I_RET_OUT`
- `V_SENSE_P`
- `V_SENSE_N`
- `ISENSE_P`
- `ISENSE_N`
- `AGND`
- `+AVDD`
- `-AVDD`
- `+5V`
- `+3V3`

## Power Architecture

### Input rails

- external input: `+5V` or `+12V`, depending on board plan

Practical board plan:

- `+5V` main input
- `+3V3` regulator for ESP32-S3 and logic
- optional `TPS65131` generates `+AVDD` and `-AVDD`

### Rail usage

| Rail | Used By | Notes |
|---|---|---|
| `+3V3` | `ESP32-S3`, digital control logic | quiet digital rail |
| `+5V` | DAC, support rails, optional analog blocks | simple main rail |
| `+AVDD` | `OPA2197`, optional analog switch supply | positive analog rail |
| `-AVDD` | `OPA2197`, optional analog switch supply | negative analog rail |
| `AGND` | ADC, DAC, analog front end | controlled analog ground |

## Current Injection Block

### Recommended structure

`MCP4725` -> `OPA2197 improved Howland current pump` -> `I_SRC_OUT`

Return path:

selected return electrode -> `I_RET_OUT` -> optional current monitor shunt / return network

### Why not keep LM358 block

Do not carry old `LM358` stage into final schematic.

Reasons:

- lower precision
- worse drift
- worse output behavior
- not good enough base for final switched tomography hardware

### Current monitor

Add precision shunt resistor in current path if practical.

Recommended nets:

- `ISENSE_P`
- `ISENSE_N`

Purpose:

- verify injected current
- normalize measurements later if needed

### Current setpoint

Use DAC to set injection amplitude.

Start conservative:

- low-frequency difference imaging
- conservative current amplitude
- do not maximize current first

## Switching Matrix

### Required switch paths

Need **four independent switch paths**:

1. `MUX_I_SRC`
2. `MUX_I_RET`
3. `MUX_VP`
4. `MUX_VN`

This biggest hardware change from Phase 2.

### MUX connections

- `MUX_I_SRC` common -> `I_SRC_OUT`
- `MUX_I_RET` common -> `I_RET_OUT`
- `MUX_VP` common -> `V_SENSE_P`
- `MUX_VN` common -> `V_SENSE_N`

Each mux channels `1..12` go to `E1..E12`.

Channels `13..16` no connect.

### Important rules

- never allow same electrode on both `I_SRC` and `I_RET`
- never allow same electrode on both `V_SENSE_P` and `V_SENSE_N`
- usually skip voltage measurements that directly include active current-drive electrodes
- firmware must block invalid combinations

## Voltage Measurement Block

### Phase 3A breadboard ADC plan

Use `ADS1115` first.

Suggested use:

- `A0` = `V_SENSE_P`
- `A1` = `V_SENSE_N`
- current monitor optional later

Good enough for first breadboard switched prototype.

### Phase 3B final ADC plan

If later needed, use `ADS131M04`:

- `AIN0` = `V_SENSE_P`
- `AIN1` = `V_SENSE_N`
- `AIN2` = `ISENSE_P`
- `AIN3` = `ISENSE_N`

Then:

- `Vmeas = AIN0 - AIN1`
- `Imeas = (AIN2 - AIN3) / Rshunt`

### Input protection

Before ADC inputs, add:

- small series resistor per ADC input
- simple RC filtering
- protection only as needed

Recommended starting idea:

- `100 ohm` to `1k ohm` series resistor near ADC input

## Suggested Connection Tables

### Electrode ring

| Electrode | `MUX_I_SRC` channel | `MUX_I_RET` channel | `MUX_VP` channel | `MUX_VN` channel |
|---|---:|---:|---:|---:|
| `E1` | 1 | 1 | 1 | 1 |
| `E2` | 2 | 2 | 2 | 2 |
| `E3` | 3 | 3 | 3 | 3 |
| `E4` | 4 | 4 | 4 | 4 |
| `E5` | 5 | 5 | 5 | 5 |
| `E6` | 6 | 6 | 6 | 6 |
| `E7` | 7 | 7 | 7 | 7 |
| `E8` | 8 | 8 | 8 | 8 |
| `E9` | 9 | 9 | 9 | 9 |
| `E10` | 10 | 10 | 10 | 10 |
| `E11` | 11 | 11 | 11 | 11 |
| `E12` | 12 | 12 | 12 | 12 |

### DAC block

| From | To | Purpose |
|---|---|---|
| `ESP32-S3 I2C SDA` | `MCP4725 SDA` | DAC control |
| `ESP32-S3 I2C SCL` | `MCP4725 SCL` | DAC control |
| `+3V3` or `+5V` | `MCP4725 VDD` | DAC supply |
| `AGND` | `MCP4725 GND` | DAC ground |
| `MCP4725 VOUT` | `OPA2197` setpoint input | controls injection current |

### Current source block

| From | To | Purpose |
|---|---|---|
| `+AVDD` | `OPA2197 supply+` | positive analog supply |
| `-AVDD` | `OPA2197 supply-` | negative analog supply if used |
| `MCP4725 VOUT` | `OPA2197 setpoint input` | sets target current |
| `OPA2197 output` | `I_SRC_OUT` | injection source common net |
| return network | `I_RET_OUT` | selected return common net |
| current shunt high side | `ISENSE_P` | optional current monitor |
| current shunt low side | `ISENSE_N` | optional current monitor |

### ADC block

#### Phase 3A breadboard ADC table

| ADC Pin/Net | Connected To | Purpose |
|---|---|---|
| `ADS1115 A0` | `V_SENSE_P` | positive sensed node |
| `ADS1115 A1` | `V_SENSE_N` | negative sensed node |
| `ADS1115 SDA` | `ESP32-S3 I2C SDA` | ADC control |
| `ADS1115 SCL` | `ESP32-S3 I2C SCL` | ADC control |
| `ADS1115 VDD` | `+3V3` | supply |
| `ADS1115 GND` | `AGND` | ground |

#### Phase 3B final ADC table

| ADC Pin/Net | Connected To | Purpose |
|---|---|---|
| `AVDD/DVDD` | per final supply plan | ADC power |
| `AIN0` | `V_SENSE_P` | positive voltage sense |
| `AIN1` | `V_SENSE_N` | negative voltage sense |
| `AIN2` | `ISENSE_P` | current shunt positive |
| `AIN3` | `ISENSE_N` | current shunt negative |
| `SPI SCLK/MISO/MOSI/CS` | `ESP32-S3` | ADC digital interface |

### Mux blocks

| Mux | Common Pin Connects To | Channels 1-12 Connect To | Channels 13-16 |
|---|---|---|---|
| `MUX_I_SRC` | `I_SRC_OUT` | `E1..E12` | no connect |
| `MUX_I_RET` | `I_RET_OUT` | `E1..E12` | no connect |
| `MUX_VP` | `V_SENSE_P` | `E1..E12` | no connect |
| `MUX_VN` | `V_SENSE_N` | `E1..E12` | no connect |

### Planned top-level connection table

#### Phase 3A breadboard-first top-level table

| Part | Pin/Net | Connects To | Notes |
|---|---|---|---|
| `ESP32-S3` | `I2C SDA` | `MCP4725 SDA` | DAC control |
| `ESP32-S3` | `I2C SCL` | `MCP4725 SCL` | DAC control |
| `ESP32-S3` | `I2C SDA` | `ADS1115 SDA` | ADC control |
| `ESP32-S3` | `I2C SCL` | `ADS1115 SCL` | ADC control |
| `ESP32-S3` | mux address/control GPIOs | all `CD74HC4067` address + enable pins | final pin map later |
| `MCP4725` | `VOUT` | `OPA2197` setpoint input | current command |
| `OPA2197` | output | `I_SRC_OUT` | source current common |
| `MUX_I_SRC` | common | `I_SRC_OUT` | route source to chosen electrode |
| `MUX_I_RET` | common | `I_RET_OUT` | route return to chosen electrode |
| `MUX_VP` | common | `V_SENSE_P` | route measured positive electrode |
| `MUX_VN` | common | `V_SENSE_N` | route measured negative electrode |
| `ADS1115` | `A0` | `V_SENSE_P` | measured voltage positive |
| `ADS1115` | `A1` | `V_SENSE_N` | measured voltage negative |

## Specific Breadboard Pinout: CD74HC4067, MCP4725, ADS1115

This is the concrete Phase 3A pinout for:

- `ESP32-S3`
- `MCP4725`
- `ADS1115`
- `CD74HC4067 x4`
- `12` electrodes

### ESP32-S3 shared buses

| ESP32-S3 Pin | Connects To | Notes |
|---|---|---|
| `3V3` | `MCP4725 VDD`, `ADS1115 VDD`, all `CD74HC4067 VCC` pins | logic/module supply |
| `GND` | all module `GND` pins | common ground |
| `GPIO8` | `MCP4725 SDA`, `ADS1115 SDA` | I2C data |
| `GPIO9` | `MCP4725 SCL`, `ADS1115 SCL` | I2C clock |

### MCP4725 pinout

| MCP4725 Pin | Connects To | Notes |
|---|---|---|
| `VDD` | `ESP32-S3 3V3` | DAC supply |
| `GND` | `GND` | common ground |
| `SDA` | `GPIO8` | I2C data |
| `SCL` | `GPIO9` | I2C clock |
| `ADDR` | `GND` | address `0x60` |
| `VOUT` | HCP/current-source setpoint input | do not connect directly to mux/electrodes |

### ADS1115 pinout

| ADS1115 Pin | Connects To | Notes |
|---|---|---|
| `VDD` | `ESP32-S3 3V3` | ADC supply |
| `GND` | `GND` | common ground |
| `SDA` | `GPIO8` | I2C data |
| `SCL` | `GPIO9` | I2C clock |
| `ADDR` | `GND` | address `0x48` |
| `A0` | `V_SENSE_P` from `MUX_VP SIG/COM` | differential positive |
| `A1` | `V_SENSE_N` from `MUX_VN SIG/COM` | differential negative |
| `A2` | optional `ISENSE_P` later | leave unused for first test |
| `A3` | optional `ISENSE_N` later | leave unused for first test |

### CD74HC4067 control pinout

Use the same address lines for all four muxes.

| ESP32-S3 Pin | Connects To | Notes |
|---|---|---|
| `GPIO4` | all mux `S0` pins | mux address bit 0 |
| `GPIO5` | all mux `S1` pins | mux address bit 1 |
| `GPIO6` | all mux `S2` pins | mux address bit 2 |
| `GPIO7` | all mux `S3` pins | mux address bit 3 |
| `GPIO15` | `MUX_I_SRC EN` | active low enable |
| `GPIO16` | `MUX_I_RET EN` | active low enable |
| `GPIO17` | `MUX_VP EN` | active low enable |
| `GPIO18` | `MUX_VN EN` | active low enable |

Set one channel number on `S0..S3`, then enable only the mux path needed.

For simple firmware, all muxes can share `S0..S3`; for more flexible firmware, give each mux its own address lines or use GPIO expanders.

### CD74HC4067 common pins

| Mux Name | CD74HC4067 `SIG/COM` Pin Connects To | Purpose |
|---|---|---|
| `MUX_I_SRC` | `I_SRC_OUT` | selected source electrode |
| `MUX_I_RET` | `I_RET_OUT` | selected return electrode |
| `MUX_VP` | `ADS1115 A0` / `V_SENSE_P` | selected voltage positive electrode |
| `MUX_VN` | `ADS1115 A1` / `V_SENSE_N` | selected voltage negative electrode |

### CD74HC4067 electrode channels

Wire every mux to the same electrode order.

| Electrode | `MUX_I_SRC` Channel | `MUX_I_RET` Channel | `MUX_VP` Channel | `MUX_VN` Channel |
|---|---|---|---|---|
| `E1` | `C0` | `C0` | `C0` | `C0` |
| `E2` | `C1` | `C1` | `C1` | `C1` |
| `E3` | `C2` | `C2` | `C2` | `C2` |
| `E4` | `C3` | `C3` | `C3` | `C3` |
| `E5` | `C4` | `C4` | `C4` | `C4` |
| `E6` | `C5` | `C5` | `C5` | `C5` |
| `E7` | `C6` | `C6` | `C6` | `C6` |
| `E8` | `C7` | `C7` | `C7` | `C7` |
| `E9` | `C8` | `C8` | `C8` | `C8` |
| `E10` | `C9` | `C9` | `C9` | `C9` |
| `E11` | `C10` | `C10` | `C10` | `C10` |
| `E12` | `C11` | `C11` | `C11` | `C11` |
| unused | `C12-C15` | `C12-C15` | `C12-C15` | `C12-C15` |

### Important limitation of shared address lines

If all four muxes share `S0..S3`, they all point to the same channel number at the same time.

That is not enough for full arbitrary `I+`, `I-`, `V+`, `V-` selection.

For full reconstruction scanning, use one of these:

1. give each mux its own `S0..S3` address lines
2. use GPIO expanders or shift registers
3. use an external decoder/control latch

The table above is good for wiring clarity, but final Phase 3 firmware needs independent mux address control.

#### Phase 3B cleaner final top-level table

| Part | Pin/Net | Connects To | Notes |
|---|---|---|---|
| `ESP32-S3` | `I2C SDA` | `MCP4725 SDA` | DAC control |
| `ESP32-S3` | `I2C SCL` | `MCP4725 SCL` | DAC control |
| `ESP32-S3` | `SPI SCLK` | `ADS131M04 SCLK` | ADC interface |
| `ESP32-S3` | `SPI MISO` | `ADS131M04 DOUT` | ADC interface |
| `ESP32-S3` | `SPI MOSI` | `ADS131M04 DIN` | ADC interface |
| `ESP32-S3` | `ADC CS` | `ADS131M04 CS` | ADC chip select |
| `ESP32-S3` | mux address/control GPIOs | all switch address + enable pins | final pin map later |
| `MCP4725` | `VOUT` | `OPA2197` setpoint input | current command |
| `OPA2197` | output | `I_SRC_OUT` | source current common |
| `MUX_I_SRC` | common | `I_SRC_OUT` | route source to chosen electrode |
| `MUX_I_RET` | common | `I_RET_OUT` | route return to chosen electrode |
| `MUX_VP` | common | `V_SENSE_P` | route measured positive electrode |
| `MUX_VN` | common | `V_SENSE_N` | route measured negative electrode |
| `ADS131M04` | `AIN0` | `V_SENSE_P` | measured voltage positive |
| `ADS131M04` | `AIN1` | `V_SENSE_N` | measured voltage negative |
| `ADS131M04` | `AIN2` | `ISENSE_P` | measured current positive |
| `ADS131M04` | `AIN3` | `ISENSE_N` | measured current negative |
| current shunt | high side | `ISENSE_P` | current monitor |
| current shunt | low side | `ISENSE_N` | current monitor |
| `TPS65131` | positive output | `+AVDD` | analog positive rail |
| `TPS65131` | negative output | `-AVDD` | analog negative rail |

## Firmware Protocol for Phase 3

Firmware should no longer emit only one simple 8-channel scan.

It should emit full frame records containing:

- selected injection pair
- selected voltage pair
- measured differential voltage
- optional measured current
- frame index

Example:

```text
FRAME:
I+,E1,I-,E2,V+,E4,V-,E5,V,-0.012345,I,0.000980
I+,E1,I-,E2,V+,E5,V-,E6,V,-0.009876,I,0.000981
...
END
```

Current Python parser does not support this yet.

Phase 3 software must add new protocol parser and `PyEIT` mapping layer.

## Suggested Measurement Protocol

Start with:

- adjacent current injection
- adjacent voltage measurement
- skip invalid / overlapping pairs

For `12` electrodes this gives enough data for useful ERT difference reconstruction.

Recommended first protocol:

1. inject between `(E1,E2)`
2. measure adjacent voltage pairs around remaining boundary
3. rotate injection to `(E2,E3)`
4. repeat until `(E12,E1)`

Keep protocol simple first.

## Schematic-Level Practical Notes

### Resistors

For current source and sensitive analog gain-setting paths:

- use `0.1%` resistors minimum
- better: matched network where possible

For improved Howland current pump, resistor matching matters a lot.

For student ERT build:

- do not stall project chasing extreme analog perfection
- good resistor matching matters more than fancy parts count

### Grounding

Use:

- separate analog ground region
- digital ground region
- single controlled connection point

Do not route ESP32 return currents through sensitive analog ground.

### Layout

Priorities:

- keep electrode switch traces short and consistent
- keep ADC inputs short
- keep current sense shunt near current path
- place decoupling at every analog IC
- keep DAC/op amp/current source compact
- separate digital lines from electrode analog lines

### Electrode connector strategy

Recommended:

- one connector block with `E1..E12`
- clear numbering clockwise
- mechanical drawing must match software numbering

Numbering mistakes will break reconstruction.

## What To Keep From Phase 2

Keep:

- `ESP32-S3`
- `MCP4725`
- `CD74HC4067`
- `ADS1115` for Phase 3A breadboard proof
- Python workflow ideas
- export / analysis habits

Do not keep as final:

- `LM358`
- one-mux sensing architecture
- line electrode layout
- saline sponge as final reconstruction phantom

## Recommended Phantom for Final Bring-Up

Use:

- circular saline tank
- evenly spaced `12` electrodes
- stable conductivity medium

Better than sponge:

- saline water tank
- agar phantom later if needed

## Bring-Up Order

### Stage 1

- power rails only
- verify `+3V3`
- verify `+5V`
- verify optional `+AVDD`
- verify optional `-AVDD`

### Stage 2

- verify DAC output
- verify op amp current source without tank
- verify current limit with dummy resistor load

### Stage 3

- verify each mux path independently
- confirm `I_SRC` routing to all `12` channels
- confirm `I_RET` routing to all `12` channels
- confirm `V+` and `V-` routing to all `12` channels

### Stage 4

- verify ADC reads selected sense pair
- compare against DMM if available

### Stage 5

- connect circular phantom
- run fixed injection pair first
- then enable full scan protocol

### Stage 6

- collect complete frames
- build new Python Phase 3 parser
- map data into `PyEIT`

## Student-Realistic Buy/Build Plan

### Buy first for Phase 3A

1. `OPA2197` or breadboard-usable breakout/adapter
2. `3` more `CD74HC4067` so total switch paths become `4`
3. `12` electrodes and circular holder/tank materials
4. precision resistors for current source

### Keep for Phase 3A

1. `ESP32-S3`
2. `MCP4725`
3. `ADS1115`
4. existing Python tooling

### Buy later for Phase 3B

1. `ADS131M04` only if `ADS1115` becomes limiting
2. `TPS65131` or similar cleaner analog power solution
3. better PCB/perfboard implementation

## Final Recommendation

For this project, Phase 3 should be:

- `12` electrodes
- circular geometry
- `OPA2197` replacing `LM358`
- improved Howland current pump
- `CD74HC4067 x4` for breadboard-first version
- keep `ADS1115` for breadboard-first version
- later upgrade ADC and analog supply only after switching architecture proven

This good enough for serious first student ERT reconstruction path without jumping to `16`-electrode hardware complexity too early.

## Practical Final Advice

For this ERT project:

- replacing `LM358` matters
- adding more mux paths matters
- circular `12`-electrode geometry matters
- `ADS1115` can stay longer than in stricter impedance-focused design

Best priority order:

1. replace `LM358`
2. add `4` switch paths total
3. move to circular `12`-electrode geometry
4. attempt ERT reconstruction
5. upgrade ADC later only if results show `ADS1115` is limiting

## Sources

- [TI OPA2197 product page](https://www.ti.com/product/OPA2197)
- [TI Improved Howland Current Pump reference](https://www.ti.com/tool/CIRCUIT060044)
- [TI ADS131M04 product page](https://www.ti.com/product/ADS131M04)
- [TI TPS65131 product page](https://www.ti.com/product/TPS65131)
