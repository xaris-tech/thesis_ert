# ADR-0062: The trough is a connected lobe, flagged when it touches an electrode

- **Status:** Accepted
- **Date:** 2026-10-13
- **Affects:** `tree_ert/absolute.py` (`trough_lobe`, `TroughLobe`, `AbsoluteResult.trough*`, `trough_index_fields`), absolute figure and Qt status line, `index.csv` columns `absolute_trough_angle_deg` and `absolute_trough_electrodes`, `absolute.npz`
- **Related:** Refines the trough of ADR-0061. Uses the ADR-0055 lobe method. ADR-0057, ADR-0058.

## Context

ADR-0061 added a trough: the single most negative element. On run
`20261013-145550-disc1-withmeasured` (hole between E2 and E5) it landed at 271 deg, on a
rim triangle beside E10, the electrode with the weakest drive current (206 uA). One
element is as fragile as the peak was, and a void cannot be told apart from a bad contact
by angle alone, because both produce a low-conductivity region at the boundary.

## Decision

The trough angle is the weighted centroid of the **lobe**: elements at or below half the
deepest log(sigma/sigma0) that are edge-connected to it (ADR-0055's half-of-peak lobe,
applied on the mesh). The lobe also lists every electrode whose node it contains. When
that list is non-empty the figure, the status line and `index.csv` say
"touches Ek: may be contact".

## Rationale

- Lobe centroid over single element: ADR-0055 measured that a connected-component centroid
  is stable to 1-2 deg across thresholds 0.5-0.6, where single-pixel and windowed
  estimates moved up to 12 deg.
- Flag rather than exclude rim elements: a real void or decay pocket can sit at the bark,
  so dropping boundary elements would hide true defects. The flag states the ambiguity.
  It does not resolve it. Rotating the belt (ADR-0059) resolves it.
- Edge connectivity rather than shared-node connectivity: two lobes meeting at a single
  vertex are kept apart.

## Consequences

- An electrode-touching trough is not evidence of a hole until a belt rotation or reseat
  shows that it stays with the wood. A trough that touches no electrode is still subject to
  ADR-0058.
- `index.csv` gains two columns. They are appended, so earlier rows read them as empty.
- `AbsoluteResult` now carries the mesh nodes, elements and electrode nodes.

## Verification

- `tests/test_absolute.py::TroughLobeTests`: connectivity, electrode flagging and the
  no-trough case on a hand-built four-triangle mesh.
- `test_strong_void_is_located_by_the_trough_not_the_peak`: the lobe locates a 0.05x void
  at 105 deg within 20 deg, and the peak misses it by more than 20 deg.
- Not yet verified on a drilled disc that passes the gates.
