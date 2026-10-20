# ADR-0063: Take the absolute colour scale from the image only

- **Status:** Accepted
- **Date:** 2026-10-13
- **Affects:** `tree_ert/absolute.py` (`display_values`, `save_absolute`)
- **Related:** Supersedes the scale rule of ADR-0061. ADR-0027 (control image on the same scale).

## Context

ADR-0061 set the shared colour scale to the larger of the image's and the noise panel's
98th-percentile |log10|. On run `20261013-175019-disc2` the split-half noise at E12, E1
and E2 reached about +-10 in log units, because those contacts changed during the scan.
The scale stretched to +-10, and the image, whose real range was about +-2, rendered pale.
That is the grey-image failure ADR-0061 was written to stop, now caused by the noise panel.

## Decision

The scale is the 98th percentile of the image's |log10(sigma/sigma0)| alone. The noise
panel is drawn on that scale and saturates where it is larger. The figure prints how many
image and how many noise elements saturated.

## Rationale

The image is what is being read; the noise panel is there to show whether noise is
comparable to it (ADR-0027). A saturated noise panel says exactly that: noise exceeds the
image. Letting noise set the scale hid the image instead. The significance gate, which
compares the two numerically, is unaffected.

## Consequences

- When noise dominates, the noise panel is a block of saturated colour. That is the
  intended reading, and the saturated count gives its extent.
- `display_values` returns a fifth value (noise elements saturated).

## Verification

`tests/test_absolute.py::DisplayScaleTests::test_huge_noise_saturates_its_panel_instead_of_flattening_the_image`.
