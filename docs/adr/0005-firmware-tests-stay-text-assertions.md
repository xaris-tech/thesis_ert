# ADR-0005: Firmware tests stay text assertions; the limitation is documented, not engineered away

- **Status:** Accepted
- **Date:** 2026-09-01
- **Affects:** `tests/test_phase3a_unified_firmware.py`, `CLAUDE.md`; how the test count may be
  cited as evidence
- **Related:** `docs/validity-audit.md` X-03, D-04

## Context

`tests/test_phase3a_unified_firmware.py` asserts against the raw text of the active `.ino` with
string and regex matches. Nothing in this repository compiles, flashes, or simulates the
firmware — there is no toolchain that could.

This is a real gap with a concrete example. D-04 (sample averaging truncated to whole ADC
counts, so `n16` bought no resolution over `n1`) was a behavioural defect in firmware that no
text assertion could have caught, and none did. It was found on the bench.

The risk is not the tests themselves — they are a legitimate doc/code sync guard and they
catch pinout and protocol drift. The risk is that a passing suite of 130 tests reads as
behavioural coverage of a system that is half firmware.

## Decision

The firmware tests remain text assertions. The limitation is stated explicitly in the module
docstring and in `CLAUDE.md`, so the pass count cannot be mistaken for evidence the firmware
works. Behavioural verification stays where it actually happens: bench sessions, recorded as
"Confirmed on hardware" entries in `docs/validity-audit.md` and `docs/planned-improvements.md`.

## Rationale

The audit's own recommendation for X-03 was to state the limitation plainly rather than build
coverage — it is listed as a documentation contradiction, not a defect.

Real behavioural firmware testing means either a PlatformIO build plus a HAL-level simulator
with mocked MCP4725/ADS1115/CD74HC4067 peripherals, or hardware-in-loop against a physically
connected board in CI. Both are substantial projects. The simulator route would test mocked
peripherals rather than the parts whose behaviour is actually in question (the analog path,
mux Ron, electrode interface), which is where every firmware defect found so far has lived.
The HIL route requires a permanently connected board.

Given that the dominant open risks in this project are analog and physical — L-01's 3.3 V rail
ceiling, L-02's current-source output impedance, electrode polarisation — engineering effort is
better spent on bench measurement than on a test harness that cannot reach those layers.

Alternatives rejected:

- **Build a simulator now.** Large effort; tests the mocks, not the analog reality.
- **Delete the text tests as misleading.** They do catch pinout and protocol drift, which is
  worth keeping. The problem was the framing, not the tests.

## Consequences

Firmware behaviour remains unverified by any automated check. Every firmware change needs a
flash-and-probe session before it can be trusted, and F8 (electrode-voltage PGA autoranging) is
currently in exactly that state — implemented, unverified.

Anyone citing this project's test count must scope the claim to host-side logic. That
constraint is now written where it will be read.

If the project later moves toward field deployment on multiple trees, this decision should be
revisited — the cost calculus changes once firmware is flashed to boards that are not on the
bench.

## Verification

The module docstring on `tests/test_phase3a_unified_firmware.py` and the corresponding note in
`CLAUDE.md`'s Tests section. This ADR records an accepted limitation rather than a capability,
so there is nothing to verify beyond the documentation being present and accurate.
