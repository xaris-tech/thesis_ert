# ADR-0074: The screen shows the tomogram alone; the full figure stays the record

- **Status:** Accepted
- **Date:** 2026-10-26
- **Affects:** `tree_ert/reconstruction.py` (`save_view`, `view_path`), `tree_ert/absolute.py` (`save_absolute`), `tree_ert/qt/main_window.py` (compact mode), `erterface-interface` (scan and review screens); what the operator sees on the Pi
- **Related:** ADR-0026 (difference image), ADR-0027 (image beside its noise control), ADR-0061 (absolute display scale), ADR-0072 (farm UI embeds the capture session)

## Context

Every run figure (`reconstruction.png`, `absolute.png`) is two panels: the image
beside its split-half noise control on one colour scale (ADR-0027), a colour
bar, and a multi-line caption with peak, significance, gate verdict and stamps.
On the Pi's 7" display the tomogram ended up about a quarter of the screen, and
the operator asked for the tomogram and its title only, with the rest in the
log.

## Decision

Each saved figure gets a display copy beside it, `<name>-image.png`, holding
the same tomogram (same values, same colour limit) and its title, with no
noise panel, no colour bar and no caption. The compact capture session and the
farm UI show the display copy. In compact mode the coloured status lines
above the images are hidden; everything they said was already written to the
log pane and `session.log`. The full figure is still written, unchanged, and
remains the record.

## Rationale

- *Change the figure itself*: would remove the noise control from the record
  and from every tool that reads it (survey, SSIM, reports). ADR-0027 exists
  so that a vivid image is never mistaken for a significant one; that still
  holds for anything saved or published.
- *Crop the full figure on screen*: brittle, and the caption would still
  overlap.
- The significance number and every stamp (NOT VALID, CROSS-SPECIMEN,
  RECIPROCITY NOT MEASURABLE) are still in the log as before, so nothing is
  lost. They are just not drawn over the tomogram on a 7" screen.

## Consequences

- On the Pi, the operator no longer sees the noise image beside the tomogram.
  Whether an image is distinguishable from noise has to be read from the log
  (`significance` / "indistinguishable from noise"). This weakens ADR-0027's
  on-screen guard, by choice, for the field screen only; the desktop
  (non-compact) window is unchanged.
- One extra PNG per image per run (~30 kB).
- Older runs without a display copy fall back to the full figure.

## Verification

`tests/test_tree_ert_qt.py::test_every_image_gets_a_tomogram_only_display_copy`;
on screen, the Reconstruction and Absolute tabs and the farm review show
`*-image.png`.
