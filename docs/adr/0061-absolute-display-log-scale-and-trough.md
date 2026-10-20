# ADR-0061: Show absolute images on a clipped log scale and report the trough

- **Status:** Accepted
- **Date:** 2026-10-13
- **Affects:** `tree_ert/absolute.py` (`AbsoluteResult.trough_*`, `display_values`, `save_absolute`), Qt Absolute tab status line, `absolute.npz`
- **Related:** ADR-0041, ADR-0042, ADR-0057, ADR-0058

## Context

Run `20261013-145550-disc1-withmeasured` (disc-01, reciprocity 6.6 %, misfit 17 %) had a
hole drilled between E2 and E5. Its Absolute tab showed a grey disc with one blue spot at
302 deg (E8-E9). Two separate problems:

1. **Display.** The colour scale was the largest |sigma - sigma0| in either panel. One
   contact spike reached +79 mS on a 2.15 mS disc (37x), so every other element, at
   sigma/sigma0 of 1.1-1.5, rendered within about 1 % of zero: grey.
2. **Summary.** The figure, status line and index reported the "peak", the element with the
   largest |sigma - sigma0|. In simulation, a void (0.05x) at 105 deg was imaged correctly
   (lowest sigma at 99 deg), but the void drags sigma0 down, so the largest |departure| was a
   *positive* overshoot at 63 deg. The same happened for a void at 302 deg (peak 274 deg,
   trough 299 deg). The peak is therefore a misleading locator for voids and decay, which is
   what the instrument is meant to find. The existing test only used a mild 0.5x inclusion,
   where the peak happens to coincide with it.

## Decision

The absolute figure plots log10(sigma / sigma0) with a symmetric colour scale clipped at the
98th percentile of |value| (image or noise, whichever is larger). The number of saturated
elements is printed on the figure. Every absolute result also reports a **trough**, the
most negative sigma - sigma0 and its angle, beside the peak.

## Rationale

- Log ratio treats 37x and 0.3x symmetrically and matches the log-resistivity presentation
  used in tree-ERT literature. Linear sigma - sigma0 lets any conductive spike dominate.
- Percentile clipping rather than a fixed scale: the scale still follows the data, and a few
  spike elements saturate visibly (the colour bar has extended ends) instead of erasing the rest.
  98 % is a judgement call: on the 145550 mesh it saturates the contact pair at E9-E10 and
  little else.
- Trough as an addition, not a replacement for the peak: the significance gate (ADR-0041) is
  defined on the peak and is unchanged, and a conductive feature (wet wood) is still found
  by the peak.
- The split-half noise panel is converted to log units to first order,
  noise / (sigma ln 10), rather than re-solving each half to keep both sigmas. It is for
  display only.

## Consequences

- Absolute peak angles reported before this ADR (e.g. disc-05's 282 deg, ADR-0057) are not
  void locations. Re-read them against the trough before citing them.
- Absolute images look busier: background variation that was always in the solution is now
  visible, including near-electrode artefacts. That variation must still be judged against
  the noise panel and ADR-0058, not read as structure.
- Saved `absolute.npz` arrays stay in mS (`sigma`, `noise`), with `trough_value` and
  `trough_angle_deg` added. Nothing downstream changes units.
- The index.csv row does not yet carry the trough.

## Verification

- `tests/test_absolute.py::test_strong_void_is_located_by_the_trough_not_the_peak`:
  a 0.05x void at 105 deg is located by the trough within 20 deg.
- `tests/test_absolute.py::DisplayScaleTests`: a 37x single-element spike is the only
  clipped element, and a 1.5x region spans more than half the colour scale.
- Re-rendering 145550 shows the hole region (E2-E5) at near background and the E9-E10 pair
  dominating, consistent with the contact reading in the 2026-10-13 discussion. Whether the
  trough finds a real hole on wood is **not yet verified**; that needs a run that passes the
  gates on a drilled disc.
