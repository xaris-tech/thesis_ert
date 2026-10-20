# ADR-0065: Absolute images use the difference-image colours: blue less, red more conductive

- **Status:** Accepted
- **Date:** 2026-10-16
- **Affects:** `tree_ert/absolute.py` (`save_absolute` colour map and colour-bar label), every
  absolute figure from this date, any figure in the thesis that shows an absolute image
- **Related:** ADR-0061 (absolute log scale and trough), ADR-0062 (trough lobe), ADR-0063
  (absolute colour scale), ADR-0026 (difference reconstruction)

## Context

The two image types used opposite colours for the same physical meaning. Difference images
(`phase3a_reconstruct` / `phase3a_unified_reconstruct`, `cmap="coolwarm"`) draw a drop in
conductivity blue and a rise red. Absolute images (`save_absolute`, `cmap="RdBu"`) drew
log10(sigma/sigma0) the other way round: red less, blue more conductive.

On 2026-10-14 the operator read a saline absolute image with the wood at E6 drawn dark red and
asked why a less conductive target was red. The colour bar was correctly labelled, but a reader
moving between the two image types had to reverse the convention each time, and a figure read
without its colour bar would be read backwards.

## Decision

`save_absolute` uses `coolwarm`, the difference-image colour map, so blue is less conductive and
red more conductive in every reconstruction this project produces. The colour-bar label now
reads `blue less, red more conductive`. Values, scale, clipping and the saved arrays are
unchanged; only the colour assignment flips.

## Rationale

- **One convention across image types** is the requirement; the difference images were the older
  and more widely used set (the 2026-10-02 SSIM series, every Qt reconstruction), so the absolute
  figure moves to match them, not the reverse.
- `coolwarm` rather than `RdBu_r`: identical meaning, and it is the exact map the difference
  images use, so the two figures are visually comparable side by side.
- Leave both as they were and rely on the colour-bar label: rejected; it already caused one
  misreading in a session where the label was on screen.

## Consequences

- Absolute PNGs made before this date have the opposite colours. The 2026-10-14 saline, disc-01
  and disc-05 absolute images were re-rendered from their recorded frames on 2026-10-16 with this
  convention; any older absolute PNG still in `scans/runs/` uses red for less conductive, and its
  own colour-bar label says so.
- A resistive target (wood, a hole, decay) now shows blue in both image types.

## Verification

- `tree_ert/absolute.py` `save_absolute`: `cmap="coolwarm"` and the label text.
- Open any absolute PNG dated 2026-10-16 or later: the colour bar reads "blue less, red more
  conductive", and a wood block in saline appears blue.
