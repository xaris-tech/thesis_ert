# ADR-0076: One tomogram style: RdBu_r, electrode dots, no target markers

- **Status:** Accepted
- **Date:** 2026-10-26
- **Affects:** `phase3a_reconstruct.draw_tomogram`, `phase3a_unified_reconstruct._draw_reconstruction`, `tree_ert/absolute.save_absolute`, every saved difference/absolute figure and its `-image.png` screen copy (ERTerface scan screen, ADR-0074)
- **Related:** ADR-0027, ADR-0074, the 2026-10-22/23 position-series contact sheets

## Context

Saved run figures used `coolwarm` with bold E-labels only, while the position-series contact
sheets (`exports/position-series-best-sheet/best_sheet.py`) used `RdBu_r` with a dot on every
electrode node. The operator found the contact-sheet look easier to read and asked for it on
ERTerface. The difference and absolute figures each drew their own `tripcolor`, so the style
lived in three places.

## Decision

All saved tomograms are drawn by one function, `phase3a_reconstruct.draw_tomogram`: flat
triangles in `RdBu_r` on a symmetric scale, a black dot at each electrode node from `el_pos`,
and plain E-labels at 1.17 x the boundary radius. The contact sheets' `x` block markers are not
carried over.

## Rationale

`RdBu_r` and `coolwarm` run in the same direction (blue low, red high), so the colour still means
blue = less conductive and nothing about a reading changes; `RdBu_r` has a whiter centre, so
"no change" reads as white rather than grey. The dots show where the electrodes physically are,
which the labels alone placed only approximately. The `x` markers marked a known block position
from the tank series' target text; a run on a disc or tree has no such ground truth in the
figure, and a marker would look like a detection. One shared function keeps the record figure,
the screen copy and the absolute figure from drifting apart again.

## Consequences

Figures saved before this change are coolwarm; mixing old and new PNGs in one sheet shows two
palettes for the same quantity. `erterface-interface/import_scans.py` crops already-saved
figures by coloured pixels and still sees the old palette for old runs. The Tkinter live plot
(`tree_ert/ui.py`, frozen per ADR-0024) and `pyeit_analyzer.py` are not changed.

## Verification

`grep -rn coolwarm phase3a_*.py tree_ert/absolute.py tree_ert/reconstruction.py` finds nothing;
a new run's `reconstruction-image.png` shows RdBu_r with 12 electrode dots. Full test suite passes.
