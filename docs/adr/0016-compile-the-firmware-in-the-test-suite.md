# ADR-0016: Compile the firmware in the test suite; behavioural verification still stays on the bench

- **Status:** Accepted
- **Date:** 2026-09-02
- **Affects:** `firmware_compile.py`, `tests/test_firmware_compiles.py`, `CLAUDE.md`'s Tests
  section, the module docstring of `tests/test_phase3a_unified_firmware.py`
- **Related:** amends [ADR-0005](0005-firmware-tests-stay-text-assertions.md) on one factual
  premise; [ADR-0015](0015-measure-output-impedance-with-the-instrument.md),
  `docs/validity-audit.md` X-03, D-04

## Context

ADR-0005 decided the firmware tests stay text assertions, on the stated premise that
"nothing in this repository compiles, flashes, or simulates the firmware — **there is no
toolchain that could**."

That premise is false as of 2026-09-02, and appears to have been false when it was written. The
Arduino IDE installed on this machine bundles `arduino-cli` at
`resources/app/lib/backend/resources/arduino-cli.exe`, and `esp32:esp32` core 3.0.0 is already
installed. The active sketch compiles as-is:

```text
Sketch uses 325593 bytes (24%) of program storage space. Maximum is 1310720 bytes.
Global variables use 14920 bytes (4%) of dynamic memory, leaving 312760 bytes.
```

A cold build takes roughly 90 seconds; with a stable `--build-path` an unchanged rebuild takes
about 6.

The gap this leaves is specific. ADR-0015 added a `HOLD` readout to `debugHold()` — real C++,
written against a text-matching test suite that would have passed just as happily on a sketch
that did not build. The only other way to find out was to flash a board attached to a living
palm. That is an expensive way to discover a missing semicolon.

## Decision

The test suite compiles the active sketch. `firmware_compile.py` locates `arduino-cli` and runs
the build; `tests/test_firmware_compiles.py` asserts the active sketch builds and fits the
ESP32-S3, and **skips** when no toolchain is installed.

ADR-0005's decision is otherwise unchanged: the text assertions stay, and behavioural
verification stays on the bench.

## Rationale

ADR-0005 weighed a simulator against hardware-in-loop and rejected both, correctly — a
simulator would test mocked MCP4725/ADS1115 peripherals rather than the analog path where every
firmware defect so far has lived, and HIL needs a permanently connected board. But a compile
check is neither of those. It is a third, much cheaper rung that the ADR did not consider,
because the premise said no toolchain existed.

It is worth being exact about what this does and does not buy, since ADR-0005's real concern was
a passing suite being mistaken for behavioural coverage:

- **Caught:** syntax errors, type errors, undeclared identifiers, a renamed function whose call
  sites were missed, a signature change that breaks a caller, wrong argument counts, a sketch
  that overflows flash or RAM.
- **Not caught:** anything ADR-0005 listed. D-04 (sample averaging truncated to whole ADC
  counts) compiles perfectly. So does a wrong pin number, an inverted mux enable, and a
  miswired current sense. Compiling proves the sketch is valid C++, not that it is correct.

The compile check therefore does not weaken ADR-0005's framing warning; it narrows the class of
defect that has to reach the bench to be found. Given that reaching the bench now means taking
the rig off a tree, that is worth 6 seconds.

Alternatives considered:

- **Leave it as ADR-0005 has it.** Rejected: the ADR's premise is factually wrong, and leaving
  it uncorrected means the next firmware change is also written blind.
- **Make it a manual script, not a test.** Rejected. A check that must be remembered is a check
  that gets skipped exactly when someone is in a hurry, which is when firmware breaks.
- **Require the toolchain and fail without it.** Rejected: it would make the suite unrunnable on
  any machine without an Arduino install, to catch a class of error that only matters to whoever
  is editing firmware. The skip keeps the suite portable.
- **Vendor the toolchain or pin the core version.** Rejected as premature. The check reports
  which `arduino-cli` it used, so a version-specific result is traceable; a build that passes
  here and fails on another core version is a real risk, but not one this project has hit.

## Consequences

The suite now depends on an external toolchain when one is present, which makes runtime
environment-dependent: about 6 seconds on this machine, zero elsewhere. `.firmware-build/` is
generated and gitignored; deleting it costs one cold rebuild.

A compile pass is now available to be over-read in exactly the way ADR-0005 warned about. The
scope statement in `CLAUDE.md` and in the text-test docstring is therefore updated rather than
removed: the firmware is compiled but still not simulated, flashed, or behaviourally tested by
anything in this repo, and "confirmed on hardware" bench notes remain the only behavioural
evidence. **The project's test count still may not be cited as evidence that the firmware
works.**

The check binds to one FQBN (`esp32:esp32:esp32s3`) and one sketch — the active unified
firmware. The older generations kept for reference are not compiled, and would likely fail if
they were, since they were written against earlier cores.

## Verification

`tests/test_firmware_compiles.py` runs the build and asserts it succeeds and fits. That the
check can actually fail was verified directly rather than assumed: a copy of the sketch with
`readCurrentUa()` renamed to a non-existent `readCurrentUaTypo()` was compiled and returned
`ok = False` with a compiler error, while the unmodified sketch returns `ok = True`. The
original sketch was not touched.

To confirm the check is live, break the sketch and run
`.\.venv\Scripts\python.exe -m unittest tests.test_firmware_compiles`. To run the compile alone:

```powershell
.\.venv\Scripts\python.exe firmware_compile.py
```

Set `ARDUINO_CLI` to override toolchain discovery. With no toolchain installed the tests skip,
which is the intended result and not a silent pass — `unittest -v` names the skip.
