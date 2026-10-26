# ADR-0068: Embed the capture session as the farm UI's scan screen

- **Status:** Accepted
- **Date:** 2026-10-25
- **Affects:** `tree_ert/qt/main_window.py` (`run_finished` signal, `compact` mode), `erterface-interface/src/erterface/capture_screen.py`, `scan_view.py`, `app.py`; what a farm-UI measurement claims
- **Related:** ADR-0024 (PyQt6 UI), ADR-0025 (scans root), ADR-0041 (absolute reconstruction), ADR-0046 (session baseline)

## Context

`erterface-interface/` is a plantation > zone > tree card UI for the 800x480 7" Raspberry Pi
display. Its scan screen was a stub (`ScanWorker`) that fabricated a 64x64 tomogram and called
it HEALTHY / AT_RISK / UNHEALTHY from the stub's maximum value. The real instrument is driven by
`tree_ert_qt.py` (`MainWindow`), which needs 1180x820 by default and a minimum of 606x706, so it
cannot be shown as-is under the farm UI's 48 px top bar (800x432 left).

## Decision

The farm UI's scan screen embeds `MainWindow(compact=True)` as a child widget under a farm header
with Back and Save to tree. Compact mode drops the title header (the run status moves to the
right column), turns Session and Log into tabs and lets the images shrink. A new
`MainWindow.run_finished(run_path)` signal enables Save to tree, which stores a farm Measurement
pointing at the run folder and its `reconstruction.png` (else `absolute.png`), classified
`UNCLASSIFIED` with no impedance ratio. Runs are recorded under `<thesis root>/scans` like any
other capture.

## Rationale

- *Port the capture logic into the farm UI*: a second capture path would drift from the one the
  thesis validates (settings gates, reciprocity, recording rules of ADR-0023/0025).
- *Launch `tree_ert_qt.py` as a separate window*: no way back to the tree, and nothing links a
  run to the tree it was taken on.
- *Keep a health verdict*: the instrument produces difference and absolute images under gates;
  nothing in this repo licenses mapping them to healthy / at-risk / unhealthy. Writing one would
  put a claim into the farm data that the thesis cannot support, so the measurement says
  UNCLASSIFIED.

## Consequences

- The farm UI imports `tree_ert` from the repository it lives in, so it only runs inside this
  checkout.
- Opening the scan screen opens a capture session: it writes `scans/session.log` and saves
  `scans/ui_settings.json` on close, exactly as `tree_ert_qt.py` does.
- The capture session stays light-themed in the farm UI's dark mode, and is not rebuilt on a
  theme toggle (that would cancel a capture).
- Farm measurements saved this way have no ratio; the CSV export and Drive payload carry it
  empty/null.
- In compact mode the left settings column still scrolls; it is long on 480 px.

## Verification

Offscreen at 800x480 (2026-10-25, Pi 5): the capture screen fits 800x432; a demo capture
emitted `run_finished`, Save to tree appended an UNCLASSIFIED measurement whose image opened on
the review screen. `tests/test_tree_ert_qt.py` covers the non-compact window. Not yet checked on
the physical 7" touchscreen.
