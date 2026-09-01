# ADR-0007: Accept either MCP4725 address, and verify binding instead of the address

- **Status:** Accepted
- **Date:** 2026-09-01
- **Affects:** `docs/current-setup-validation-runbook.md` (step 2), `tree_ert/selftest.py`
  (DAC binding check), bench procedure
- **Related:** `docs/validity-audit.md` X-01

## Context

The validation runbook's step 2 required the I2C scan to report the MCP4725 at `0x61`, and the
2026-09-01 session handoff went further, naming `0x60` as a known stale-doc trap to watch for.

On the bench that day the board reported the opposite:

```
STATUS,2,...,SHUNT_OHMS,97.90,DAC_ADDR,0x60,...
I2C_SCAN,BEGIN / I2C_DEVICE,0x48 / I2C_DEVICE,0x60 / I2C_SCAN,END,FOUND,2
```

The DAC is at `0x60`, the firmware bound to `0x60`, and the board is healthy — rungs 5 and 6
went on to return 216/216 `Q,OK` at a 677 uA median. A runbook check asserting `0x61` would
have failed working hardware and sent the next person hunting a fault that does not exist.

The MCP4725's A0 strap sets the low address bit, so `0x60` and `0x61` are both legitimate for
this part. Which one appears depends on how the board was strapped, and this project has
scanned at both across builds. The address alone therefore carries no health information.

## Decision

The runbook and the self test accept an MCP4725 at either `0x60` or `0x61`. What they check
instead is that the address the firmware bound (`DAC_ADDR` in `STATUS`) matches an address
that actually answered the scan.

## Rationale

The real failure this check should catch is a DAC that is not bound, or bound to something
that isn't there — writes go nowhere and the DAC silently never moves. Binding-versus-scan
agreement catches that on either address.

Alternatives rejected:

- **Assert `0x61`, as the runbook did.** Falsified on the bench the same day it was written.
- **Assert `0x60` instead.** Same defect with the numbers swapped; the next differently
  strapped board fails again.
- **Pin the strap in hardware and assert the pinned value.** Correct in principle, but it
  requires a board change to fix a documentation defect, and does nothing for the boards that
  already exist.

## Consequences

Easier: the runbook stops failing healthy hardware, and the same procedure covers boards
strapped either way.

Harder: a genuinely mis-strapped board — two MCP4725s, or one at an unexpected address — is no
longer caught by the address check. `select_dac_address` already refuses to guess when both
`0x60` and `0x61` answer, which is the case that actually matters; that refusal is now the
sole guard.

This commits the project to treating the I2C address as configuration, not as an invariant.
`b<hex>` remains the runtime override.

## Verification

`tests/test_phase3a_unified_reconstruct.py::TestDacAddressDiscovery` covers the selection
rules, including the refusal to choose when both candidates answer.

On hardware: send `i` and `?`, and confirm the address in `DAC_ADDR` appears in the scan
output. Falsified if a board binds an address the scan never reported.
