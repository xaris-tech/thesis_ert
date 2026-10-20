# Run 20261020-154712-saline-empty-rpi-adjacent-dac400-st10-n16

- **Captured:** 2026-10-20T15:47:12
- **Code version:** `2f8c162`
- **Label:** saline-empty-rpi-adjacent-dac400-st10-n16

## Conditions

| Field | Value |
|---|---|
| medium | saline tank |
| saline_g_per_l | _not recorded_ |
| fill_depth_mm | _not recorded_ |
| water_temp_c | _not recorded_ |
| electrode_protrusion_mm | _not recorded_ |
| grounding | unknown |
| tank_contents | empty tank (no wood) |
| target_description | empty tank (no wood) |
| electrode_map | E1 = marked nail, clockwise viewed from above |
| specimen_id | saline-tank |
| circumference_mm | _not recorded_ |
| thickness_mm | _not recorded_ |
| major_diameter_mm | _not recorded_ |
| minor_diameter_mm | _not recorded_ |
| operator | _not recorded_ |
| notes | 2026-10-20 first capture with ESP32-S3 on Raspberry Pi 5 host (/dev/ttyACM0); same tank as afternoon runs; saline g/L, temp, depth not measured |

## Instrument settings

| Setting | Value |
|---|---|
| port | /dev/ttyACM0 |
| baud | 115200 |
| pattern | adjacent |
| current_range | high |
| dac | 400 |
| settle_ms | 10 |
| samples | 16 |
| warmup_frames | 10 |
| target_warmup_frames | 5 |
| baseline_frames | 10 |
| frames | 20 |
| diameter_cm | None |
| log_dir | phase3a_logs |
| log_enabled | True |
| allow_unstable_baseline | False |
| lenient_quality | False |
| filter_pairs | True |
| electrode_offset | 0 |
| electrode_reversed | False |
| self_test_frames | 3 |
| expected_shunt_ohms | 97.9 |
| absolute_exclude_electrodes | () |

## Incomplete

These were not recorded at capture time and cannot be recovered later:

- grounding is not recorded (floating or grounded?)

## Notes

2026-10-20 first capture with ESP32-S3 on Raspberry Pi 5 host (/dev/ttyACM0); same tank as afternoon runs; saline g/L, temp, depth not measured
