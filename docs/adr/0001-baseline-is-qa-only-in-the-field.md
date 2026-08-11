# Baseline is QA-only in the field; difference imaging stays on the bench

Difference reconstruction requires scanning the same physical sample before and after a change. A standing living coconut tree cannot be scanned before it became diseased, so subtracting two same-session tree scans yields only drift and noise — not an image of the trunk interior. We therefore split the concept: an **imaging baseline** exists only on the bench (saline phantom, cut-trunk pilot), while a **field QA baseline** on a tree proves acquisition stability and admits or rejects that session's data, and is never subtracted to form a tree image. The healthy/asymptomatic/diseased comparison rides on normalized raw measurements and reconstruction-derived summary features, not on a tree difference image.

## Considered Options

- **Absolute reconstruction against a homogeneous forward model** — would produce a tree image with no time baseline, but is far more sensitive to electrode geometry, contact impedance, and trunk shape than difference imaging, and is a substantial new build. Rejected as too risky for the thesis timeline.
- **Cross-tree baseline** (scan a healthy tree, subtract a diseased tree) — rejected because differing trunk diameters and electrode placements make the difference dominated by geometry rather than health.

## Consequences

- Baseline stability work is not merely a preliminary: a stable field QA baseline becomes the admission criterion for a tree's data.
- No difference reconstruction image may be presented as evidence about a standing tree.
- The classification path requires feature extraction from raw measurements, which does not exist in the codebase yet.
