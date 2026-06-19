# System Architecture

## Signal Flow

```text
Windows laptop GUI
    | USB serial
ESP32-S3
    |-- I2C --> MCP4725 --> OPA2134PA Improved Howland source
    |-- GPIO --> MUX_I_SRC / MUX_I_RET --> 12 electrodes
    |-- GPIO --> MUX_VP / MUX_VN --------> 12 electrodes
    `-- I2C <-- ADS1115 <-- voltage pair and return-current shunt
```

## Power Flow

```text
Laptop USB --> ESP32-S3 --> 3.3 V logic/ADC/DAC/mux modules

12 V DC router adapter
    --> positive/negative converter
    --> +9 V / GND / -9 V
    --> OPA2134PA analog current source
```

The converter center ground and ESP32 ground meet at one controlled common
point. The negative rail is never connected to a logic pin or the ESP32 `3V3`
rail.

## Measurement Cycle

1. Set current command to idle and disable all muxes.
2. Address the source, return, voltage-positive, and voltage-negative muxes.
3. Enable the selected paths.
4. Apply the selected current command and wait for settling.
5. Measure shunt voltage and electrode differential voltage.
6. Disable the paths.
7. Repeat with source and return electrodes reversed.
8. Correct offsets, normalize by measured current, and store the record.

## Key Electrical Constraint

The CD74HC4067 modules run at 3.3 V. Every mux analog terminal must therefore
remain approximately between ground and 3.3 V. The OPA2134 supply may be
`+/-9 V`, but that does not permit a mux or ADS1115 input to see those rails.
Current range and load compliance must be verified with a multimeter before
connecting the electrode matrix.

