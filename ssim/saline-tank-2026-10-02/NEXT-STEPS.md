# Next steps

Captures for the simplified plan are complete: 12 single-block positions,
centre, and 6 opposite pairs, 19 scored runs in all. What is left:

## 1. Photos — 18 of 19 done, one question now unanswerable

18 photos are in `photos/`, renamed to `<run_id>.jpg` and indexed in
`photos/PHOTO-INDEX.csv` (joined to each run's scores) and
`photos/SSIM-REFERENCE.csv` (with empty-tank and perfect-placement reference
scores).

**`20261002-173951` has no photograph and there is no plan to get one** — the
tank has been taken down. So the E3+E9 / E3+E10 ambiguity **cannot be settled**.
The run stays relabelled to the plan (E3+E9) and marked UNCONFIRMED, and its
ground truth remains partly inferred from its own result. Do not present it as a
confirmed localisation, and do not use it in the 22-of-24 headline count without
saying so.

Checked against the photos, and worth a decision:

1. **E6, both placements read high** (`144734` +18°, `180403` +15°). The E6 peak
   landed at 48°, which is 18° from E6 (30°) but only 12° from E5 (60°) — biased
   toward E5. In the photo the block does look rotated off the E6 radial toward
   the E5/E4 side. **If the block was physically offset toward E5, the instrument
   was right and the ground truth is wrong**, and those runs need relabelling
   rather than an error column. Not confirmed — the photos have no ruler and the
   camera is not directly overhead.
2. **E5, `144109` +9°** (peak 69°, past E5 toward E4). Same check, same
   uncertainty.
3. `180403` (E6+E12): the two blocks in the photo do not look like the same
   object. If so, that pair is not a clean two-identical-blocks test and its
   SSIM is not comparable with the others.

None of these is resolvable to better than roughly ±10° from these photos. Treat
them as open.

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

Both outputs are **regenerated from scratch**, so do not hand-edit them or add
columns — the edit is lost on the next run. `photos/PHOTO-INDEX.csv` and
`photos/SSIM-REFERENCE.csv` are the hand-curated companions and are not touched
by this command.

Re-scoring alone will not change any conclusion, because `ssim_eval.py`
reconstructs with a default `UiSettings` built from the pattern alone. That is
correct for this series only because **all 27 runs happen to have used
`electrode_offset = 0` and `electrode_reversed = false`** — verified. Had any
run been recorded under a rotated or reversed electrode map, its SSIM would have
been computed against the wrong mask with no warning.

## 4. Optional captures, if the tank is set up again

Use the same settings, and take a fresh baseline before each group.

- Centre repeat ×2, and one pair repeat (E1+E7): measures how much the score
  changes when a block is placed again at the same spot.
- **An empty-tank control, and this is now the highest-value capture in the
  list.** A baseline followed by a second empty capture, scored the same way,
  measures what this instrument and this metric return when there is provably
  nothing there. The predicted answer is already known — `SSIM-REFERENCE.csv`
  puts an all-zero image at 0.90–0.96 — but that is computed, not measured. One
  real capture turns the whole SSIM section from unusable into a baseline it can
  be read against. Photograph it too.
- **A ruler in frame** in every photo, so the radius ground truth stops being the
  assumed 128/160 mm ratio. The existing 18 photos cannot be retro-fitted.
- E2+E8 again right after a fresh baseline. The redo `181205` came 66 minutes
  after its baseline.

## 5. For the thesis

- **Headline: angle localisation.** |error| ≤ 12° on 22 of 24 angled block
  placements (the centre run has no angle), every target detected. One of the 24
  (`173951`) has no photographic ground truth and is relabelled from its own
  result — say so where the number is quoted.
- **Do not quote the SSIM values.** An empty tank scores 0.90–0.96 on the same
  metric; all 19 runs score 0.28–0.59, i.e. below empty. The metric averages
  over the whole disc while the mask is ~1 % of it. See the SSIM summary in
  `README.md`. This needs a fix in `tree_ert/ssim.py` and an ADR superseding
  ADR-0045 before any SSIM number goes in the text.
- State the radial pull toward the centre (blocks at 0.8 R appear at about
  0.27–0.61 R) as a limitation of the one-step JAC reconstruction (ADR-0044,
  ADR-0045), and state that the 0.8 R ground truth is itself assumed — no photo
  has a ruler in frame.
- The wedge search has no radial bound, so a centre-collapsed artefact could be
  reported as a clean localisation. The angle result is trustworthy because the
  photo shows the angle; it is not trustworthy because the search found a blob
  in the right wedge.
- Only compare SSIM values within this series — and only after the metric is
  fixed.
