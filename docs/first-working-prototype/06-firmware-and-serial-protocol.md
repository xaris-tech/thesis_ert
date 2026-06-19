# Firmware and Serial Protocol

## Unified Firmware

Replace the separate adjacent and opposite firmware images with one Arduino
IDE build. Protocol changes happen through serial commands, not reflashing.

Required commands:

| Command | Purpose |
|---|---|
| `STATUS` | return firmware/protocol version and settings |
| `MODE,ADJACENT` | adjacent drive and adjacent voltage measurements |
| `MODE,OPPOSITE` | opposite drive and adjacent voltage measurements |
| `DAC,<code>` | set validated DAC command |
| `SETTLE,<ms>` | set post-switch delay |
| `SAMPLES,<n>` | set samples per differential reading |
| `FRAME` | capture one complete polarity-reversed frame |
| `STOP` | disable current and all muxes |
| `SELFTEST` | report I2C devices and safe idle state |

## Safe Switching State Machine

1. Command current idle.
2. Disable all muxes.
3. Write all addresses.
4. Enable required muxes.
5. Apply drive command.
6. Wait for settling.
7. Read current and voltage samples.
8. Return to idle and disable muxes.
9. Swap source/return and repeat.

Never change an address while that mux is enabled and carrying current.

## Record Contract

Every frame begins with versioned metadata and ends explicitly. Each record
contains:

- frame ID and timestamp;
- adjacent/opposite pattern;
- forward/reverse polarity;
- I+, I-, V+, and V- electrode numbers;
- measured differential voltage in mV;
- measured shunt voltage or current;
- DAC code and timing settings; and
- quality/error flags.

Example shape:

```text
FRAME,2,104,ADJACENT
M,FWD,E1,E2,E3,E4,-12.345,0.0987,300,OK
M,REV,E2,E1,E3,E4,12.210,-0.0985,300,OK
END,104,OK
```

The parser must reject version mismatches, missing combinations, duplicate
records, unsafe values, and frames whose declared mode differs from the app.

