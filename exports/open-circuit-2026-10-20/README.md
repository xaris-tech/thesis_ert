# Open-circuit leak check, 2026-10-20

Follow-up to the 2026-10-19 open-circuit leak (156 µA at DAC 620, 49 µA at DAC 100, nothing
attached; see `docs/handoff-2026-10-19/README.md` §2.1). Decision recorded in
[ADR-0066](../../docs/adr/0066-accept-residual-e10-e12-board-leak.md).

## Method

`open_circuit_check.py [rounds]` (COM7, adjacent, settle 10 ms, 16 samples, high range,
`lenient_quality=True`). Each round: 3 frames at DAC 620, then 3 at DAC 100. Each line prints the
frame's median and maximum |current|, the count of records not marked OK, and the median
|current| per drive electrode.

**Electrode labels in the logs are 0-based** (`E0`..`E11` = physical E1..E12): log `E9 E10 E11`
are physical E10, E11, E12.

Nothing touched the free lead ends in any step. Battery (current-source supply) on, except log 03.

## Results

| Log | State | Max at DAC 620 | Max at DAC 100 | Drive medians, physical E10/E11/E12 at DAC 620 |
|---|---|---|---|---|
| 01 | Board only, after first clean, 6 rounds | 159 µA first frame, ~14 µA from frame 3 | 121 µA once, else ~14 µA | 11 / 12 / 3 µA |
| 02 | Board only, after second clean + corroded wires replaced, 6 rounds | 13.6–14.2 µA | 3.9–4.1 µA | 7 / 10 / 3 µA |
| 03 | Leads 1–3, **battery off: invalid** | ≤1.2 µA | ≤1.1 µA | 0 / 0 / 0 µA |
| 04 | Leads 1–3, 2 rounds | 12.5–13.3 µA | 3.8–3.9 µA | 6–7 / 9 / 3 µA |
| 05 | Leads 1–6, 1 round | 10.8–12.0 µA | 3.8–5.1 µA | 5–6 / 7–8 / 2–3 µA |
| 06 | Leads 1–9, 1 round | 9.8–10.0 µA | 3.2–3.3 µA | 5 / 7 / 2 µA |
| 07 | All 12 leads, 1 round | 12.3–12.5 µA | 3.8–4.1 µA | 6 / 8–9 / 2–3 µA |

Frame median current was 0.0–0.3 µA in every valid log. Drives on physical E1–E9 stayed at
0–1 µA throughout.

## Findings

1. Cleaning took the leak from 156 µA to a frame median of ≤0.3 µA.
2. The first-frame spike seen after the first clean (159 µA) disappeared after the second clean and
   the wire replacement.
3. The leads add no measurable leak: adding them three at a time left every drive within the
   board-only range.
4. A residual leak of about 7–10 µA remains on the board when driving physical E10/E11 (worst
   record about 12–14 µA). It scales with the DAC code (about 3× lower at DAC 100), so it is a
   resistive path, not an offset. It is present with no leads attached, so it is on the board, on
   or around the E10/E11 multiplexer channels.
5. About 198–216 records per frame are marked not OK. That is expected with open terminals.

This check does not test the E1/E2 channel fault (ADR-0064); that needs a loaded saline run.
