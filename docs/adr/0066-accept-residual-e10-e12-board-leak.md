# ADR-0066: Accept the residual E10–E12 board leak and check it every session

- **Status:** Accepted
- **Date:** 2026-10-20
- **Affects:** bench methodology, thesis claims about specimens near E10–E12 and low-current specimens
- **Related:** ADR-0064 (E1/E2 exclusion), `docs/handoff-2026-10-19/README.md` §2.1 and §3.1, `exports/open-circuit-2026-10-20/`

## Context

On 2026-10-19 the instrument drove 156 µA at DAC 620 (49 µA at DAC 100) with nothing attached,
every record marked OK; on 2026-09-22 the same check gave 0.8 µA. The leak was largest when driving
E9–E11 (198–203 µA).

On 2026-10-20 the board was cleaned twice with IPA, and corroded or rusted wires were replaced. The
open-circuit check (`exports/open-circuit-2026-10-20/`) then gave:

- frame median 0.0–0.3 µA (was 156 µA);
- no first-frame spike after the second clean (the first clean still showed 159 µA on frame 1);
- adding the electrode leads three at a time (1–3, 1–6, 1–9, 1–12) changed nothing: the leads are clean;
- a residual leak with no leads attached of about 7–10 µA median when driving physical E10/E11
  (and 2–3 µA on E12), worst single record 12–14 µA at DAC 620, about 4 µA at DAC 100.

The residual scales with the DAC code, so it is a resistive path of a few hundred kΩ on the board,
on or around the E10/E11 multiplexer channels. The operator has decided not to repair it further
for now.

## Decision

The residual leak is accepted as a known limitation. The open-circuit check runs at the start of
every session, before any specimen is mounted; a session goes ahead only if the worst record at
DAC 620 is ≤20 µA and drives other than E10–E12 stay ≤2 µA. Specimens whose median drive current
is below about 300 µA (dry discs such as disc-10 at about 90 µA) are not imaged until the leak is
repaired.

## Rationale

- **Repair now** (inspect and rework the E10/E11 mux pins, or replace the CD74HC4067): the correct
  fix, but declined by the operator after two cleans. It stays the open item.
- **Exclude E10–E12 from the solve, as ADR-0064 does for E1/E2:** removes three more electrodes
  for a bias that is about 1–3 % of the drive current at normal loads. Combined with the E1/E2
  exclusion it would leave only half the ring, which is worse than the bias.
- **Correct for the leak in software** (subtract a measured open-circuit current): the leak path
  is in parallel with the load, so the correction depends on the load's own impedance and is not
  a constant. Not attempted.
- **Accept with a current floor:** at 300–1000 µA (saline, moist discs) a 10 µA leak is 1–3 %,
  below the 15 % reciprocity and misfit gates. At about 90 µA it is about 10 %, which is not
  negligible next to the contrast a hole produces. Hence the 300 µA floor. The 20 µA session
  threshold is about 1.5× the worst record measured on 2026-10-20, so a regrowing leak is caught
  before it reaches the 2026-10-19 level.

## Consequences

- Images near E10–E12 carry a small bias. A trough touching E10/E11 on a specimen expected to be
  intact must not be read as wood until checked against the leak.
- Dry specimens stay out of scope until the board is repaired.
- Every session now starts with about 4 minutes of open-circuit checking (one round). Results go
  in the session notes or the run's conditions notes.
- When the board is repaired, this ADR is superseded and the current floor is dropped.

## Verification

Run `exports/open-circuit-2026-10-20/open_circuit_check.py 1` with nothing attached and the
current-source battery on. The 2026-10-20 logs are the reference. Not automated yet: the check is
a candidate self-test item in `tree_ert/selftest.py` (handoff §3.1 step 4).
