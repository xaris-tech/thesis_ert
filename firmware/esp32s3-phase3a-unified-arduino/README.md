# ESP32-S3 Phase 3A Unified ERT Firmware

Arduino IDE firmware for the complete 12-electrode Phase 3A breadboard:

- four independently addressed CD74HC4067 muxes;
- MCP4725-controlled OPA2134 Improved Howland current pump;
- ADS1115 A0-A1 differential electrode voltage;
- ADS1115 A2-A3 differential voltage across the return shunt;
- adjacent, skip-1, skip-2, or opposite drive selected at runtime; and
- forward and reverse injection captured back to back for each sense pair.

Forward and reverse are interleaved per sense pair rather than run as two
separate passes. Holding one polarity across a whole injection pair lets an
ionic double layer build on the electrodes, which shows up as current decaying
across a fixed drive pair and as forward/reverse voltages that stop inverting.

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
| `p100` | request DAC code 100 during measurements, clipped to the active range ceiling |
| `t10` | set 10 ms settling time |
| `c0` | set post-measurement discharge time in ms; `0` disables |
| `n4` | average four ADC conversions |
| `el` | select LOW current range: Rs 68 ohm, DAC ceiling 420 |
| `em` | select MEDIUM current range: Rs 22 ohm, DAC ceiling 680 |
| `eh` | select HIGH current range: Rs 10 ohm, DAC ceiling 620 |
| `j97.9` | set the current-sense shunt value in ohms |
| `a1` / `a0` | enable or disable electrode-voltage PGA autoranging |
| `g` | start continuous frames |
| `x` | stop and force DAC/muxes idle |
| `i` | scan I2C bus for MCP4725 and ADS1115 |
| `b60` / `b61` | set the MCP4725 I2C address (hex); `b` alone reports the active one |
| `d` | hold E1/E2 driving and E3/E4 sensing for multimeter work |
| `?` | print status |
| `h` | print help |

The `p` command stores the requested drive level but leaves the physical DAC
at zero while idle. The firmware applies it only after all mux addresses are
set and enabled.

### Current range

The `e` commands select which Rs jumper is physically fitted and enforce the
matching DAC ceiling from
`docs/first-working-prototype/03-howland-current-source.md`. The firmware boots
in LOW because that document requires bring-up to start on the lowest range;
set the range to match the fitted resistor before scanning. Lowering the range
also lowers a DAC request that exceeds the new ceiling, and reports that it did.

### Electrode-voltage autoranging

The electrode-voltage channel picks its PGA range per measurement instead of
sitting on a fixed `GAIN_ONE`. Each read takes one throwaway conversion on the
widest range to size the signal, selects the tightest range that still fits it
with 25 percent headroom, and then runs the averaged read there. If the signal
grows between the two and the tight range clips, it falls back to the widest
range and re-reads.

| Range | Full scale | One step |
|---|---:|---:|
| `GAIN_SIXTEEN` | +/-256 mV | 7.8 uV |
| `GAIN_EIGHT` | +/-512 mV | 15.6 uV |
| `GAIN_FOUR` | +/-1024 mV | 31.3 uV |
| `GAIN_TWO` | +/-2048 mV | 62.5 uV |
| `GAIN_ONE` | +/-4096 mV | 125 uV |

Why it matters: measured saline frames put every electrode voltage under 250 mV
while the fixed range was +/-4096 mV, so a single step was 125 uV - larger than
the injected IR drop on electrode pairs far from the injection pair. Forward and
reverse then landed on the same ADC code and their difference came out exactly
zero, which is what the host's offset check reports as an offset-dominated pair.

`?` reports `VGAIN_AUTO` and `VRANGE_MV` (the range used by the most recent
read). `a0` pins the channel back to `GAIN_ONE` for comparison.

The current-sense channel is not autoranged: it already sits on `GAIN_SIXTEEN`,
the finest range, and a 1 mA full-scale current across the shunt stays well
inside +/-256 mV.

### Shunt value

`j` sets the current-sense shunt in ohms and `?` reports it. The shunt is the
resistor between `MUX_I_RET` SIG/COM and ground that A2/A3 measure across - not
Rs, which is the current-setting resistor inside the Howland network. A shunt
value that does not match the fitted part scales every reported current.

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

- Firmware calculates current from the configured shunt value (default 97.9 ohm, set with `j`) and clips DAC commands to the ceiling of the active current range.
- Set the current range with `el`/`em`/`eh` to match the fitted Rs jumper before scanning. The firmware boots in LOW.
- Start with `p100`.
- Never allow any CD74HC4067 analog pin or ADS1115 input outside 0-3.3 V.
- Verify I_SRC_OUT remains below 3.0 V with a multimeter before mux connection.
- `x` or reset forces a zero DAC command and disables all muxes.
