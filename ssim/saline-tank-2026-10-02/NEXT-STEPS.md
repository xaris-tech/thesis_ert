# Next steps

Captures for the simplified plan are complete: 12 single-block positions,
centre, and 6 opposite pairs, 19 scored runs in all. What is left:

## 1. Photos — needed to close the series

Put one top-down photo per target run in `photos/`, named by run ID (see
`photos/README.md`). Priority:

1. `20261002-173951`: was it **E3+E9** (the plan) or **E3+E10** (the typed
   text)? The run is relabelled to the plan and marked unconfirmed until
   then.
2. `20261002-144734` and `20261002-180403`: both E6 placements read high
   (+18°, +15°). Was the block offset toward E5?
3. `20261002-144109` (E5, +9° in the UI).
4. All others.

## 2. Record the missing conditions

Saline g/L, fill depth, water temperature and grounding were never recorded.
Estimate them if they cannot be measured, write them into the README, and
mark them as estimates.

## 3. Re-score after any relabel

```powershell
.\.venv\Scripts\python.exe ssim_eval.py ssim/saline-tank-2026-10-02
```

It writes `ssim_results.csv` and `ssim_contact_sheet.png` here. It scores the
manifest's `target` rows, using each run's `target_description` from
`conditions.json`. Add `--since RUN_ID` to include later runs from
`scans/runs` that are not in the manifest yet.

## 4. Optional captures, if the tank is set up again

Use the same settings, and take a fresh baseline before each group.

- Centre repeat ×2, and one pair repeat (E1+E7): measures how much the score
  changes when a block is placed again at the same spot.
- One control: a baseline followed by a second empty capture. It should
  score under 2×.
- E2+E8 again right after a fresh baseline. The redo `181205` came 66 minutes
  after its baseline.

## 5. For the thesis

- Headline: angle localisation, |error| ≤ 12° for 22 of 24 angled block placements (the centre run has no angle),
  every target detected.
- Quote raw and blurred SSIM next to it, and state the radial pull toward the
  centre (blocks at 0.8 R appear at about 0.35–0.6 R) as a limitation of the
  one-step JAC reconstruction (ADR-0044, ADR-0045).
- Only compare SSIM values within this series.
