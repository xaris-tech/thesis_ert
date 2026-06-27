# ESP32-S3 HCP Test Firmware

This Arduino IDE sketch tests the MCP4725 and OPA2134PA Improved Howland
current pump without connecting the electrode muxes.

## Required Arduino Library

Install `Adafruit MCP4725` through Arduino Library Manager.

## Wiring

| MCP4725 | ESP32-S3 |
|---|---|
| VDD | 3V3 |
| GND | GND |
| SDA | GPIO8 |
| SCL | GPIO9 |
| ADDR | GND, if exposed |
| VOUT | HCP Vp through R3 = 5 kohm |

## Use

1. Open `esp32s3_hcp_test/esp32s3_hcp_test.ino` in Arduino IDE.
2. Select the correct ESP32-S3 board and COM port.
3. Upload the sketch.
4. Open Serial Monitor at 115200 baud with newline enabled.
5. Send `p100`, verify the dummy-load current, then try `p200` and `p300`.
6. Send `o` before changing dummy loads or wiring.

The sketch is configured for `Rs = 10 ohm` and clips commands above DAC code
620, approximately 1 mA with a measured 3.3 V DAC supply. Begin at `p100` and
increase only after dummy-load and shunt measurements pass.
