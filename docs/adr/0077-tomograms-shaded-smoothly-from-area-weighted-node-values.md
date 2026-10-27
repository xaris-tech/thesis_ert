# ADR-0077: Tomograms are shaded smoothly from area-weighted node values

- **Status:** Accepted
- **Date:** 2026-10-27
- **Affects:** `phase3a_reconstruct.draw_tomogram`, `phase3a_reconstruct.element_to_node`, every saved difference/absolute figure and its `-image.png` screen copy
- **Related:** ADR-0076 (supersedes its "flat triangles" clause only), ADR-0061, ADR-0062

## Context

ADR-0076 drew every tomogram as flat triangles. The solver returns one value per mesh
element, so each triangle showed as its own facet. On the operator's screen the images
read as a mosaic of triangles; the operator asked for them to look smooth.

## Decision

`draw_tomogram` averages each element's value onto its three corner nodes, weighted by
element area (`element_to_node`), and draws with `tripcolor(shading="gouraud")`. Palette,
symmetric scale, electrode dots and labels are unchanged from ADR-0076.

## Rationale

- **Gouraud on node values** is the standard way to shade a per-element field on a triangle
  mesh without inventing data; a constant field stays exactly constant.
- **Area weighting** keeps small boundary elements from dominating a node shared with large
  interior ones.
- **Rejected: resampling onto a grid and smoothing with a kernel.** It adds a smoothing radius
  as a free parameter and blurs further than the mesh does.
- **Rejected: keeping flat shading.** It is the literal solver output, but the facets suggest
  a precision the reconstruction does not have.

## Consequences

- The picture is a display interpolation. Each colour peak is a little shallower than the
  deepest single element, because each node averages its neighbours. Every reported number
  (trough, peak, sectors, significance, misfit) is still computed from the per-element values
  and is unchanged.
- Figures saved before this change are faceted; mixing old and new PNGs shows both styles.
- The Tkinter live plot (frozen, ADR-0024) and `update_reconstruction_plot` stay flat.

## Verification

`element_to_node` of a constant field returns that constant at every node. A redraw of
`20261027-125810-disc-08-b1b-opposite/absolute.npz` shows the same features in the same
places as the flat rendering, without facets.
