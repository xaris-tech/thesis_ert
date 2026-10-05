"""SSIM of a difference image against a ground-truth block mask (ADR-0044, ADR-0045).

Offline and solver-agnostic: everything here works on a recorded run's
reconstruction and the target text the operator typed, so a whole series can be
scored with no board attached.

Three numbers per run, deliberately reported together:

- ``ssim_raw``: SSIM against the sharp block footprint. The JAC solver pulls
  targets toward the centre and blurs them (ADR-0044), so a correct detection
  still scores low here. This number grades the solver as much as the
  instrument.
- ``ssim_blurred``: SSIM against the footprint convolved with a Gaussian of
  ``psf_sigma``. That asks "is the blob where it should be, at the resolution
  this system has?"
- ``angle_error_deg``: per block, the strongest resistive pixel inside the
  block's ±45° wedge, compared with the true angle. This is the headline
  (ADR-0044).

The tank geometry comes from the mesh's own electrode nodes (``el_pos``), not
from an assumed ``180 - 30k`` convention, so a change in PyEIT's electrode
placement cannot silently rotate every mask.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from scipy import ndimage

TANK_RADIUS_MM = 160.0
NEAR_RADIUS_MM = 128.0
"""'Near Ek' in the 2026-10-02 series: block centre this far from the tank centre."""

BLOCK_FOOTPRINT_MM = (23.0, 22.0)
"""Wooden block footprint, tangential x radial, standing upright."""

GRID = 64
"""Raster side in pixels across the unit disc; 2/64 R = 5 mm per pixel at R = 160 mm."""

PSF_SIGMA = 0.2
"""Blur applied to the mask for ``ssim_blurred``, in units of tank radius (ADR-0045)."""

SSIM_SIGMA_PX = 1.5
"""Gaussian SSIM window, the Wang et al. (2004) default."""

WEDGE_DEG = 45.0
CENTRE_SEARCH_R = 0.4

REGION_DILATE_PX = 2
"""How far the block mask is dilated to form the region ``ssim`` averages over.

The mean must not be taken over the whole disc. The mask is 16-42 px of a
3228 px disc, so across the remaining ~99% both rasters sit near zero and the
luminance term carries SSIM to ~0.95 for *any* image whatsoever, an empty tank
included. On the 2026-10-02 saline series that put all 19 runs (0.28-0.59)
below an empty tank (0.90-0.96), which made the number unusable.

Two pixels puts the mask at ~36% of the region, enough that structure inside
the mask has to agree for the score to rise, while leaving room for the solver's
own blur so a detection is not punished for being diffuse.
"""


@dataclass(frozen=True)
class Block:
    """One block's true centre in unit-disc coordinates."""

    label: str
    x: float
    y: float

    @property
    def radius(self) -> float:
        return float(np.hypot(self.x, self.y))

    @property
    def angle_deg(self) -> float:
        return float(np.degrees(np.arctan2(self.y, self.x)) % 360.0)


@dataclass
class BlockScore:
    label: str
    true_angle_deg: float | None
    peak_angle_deg: float | None
    angle_error_deg: float | None
    true_radius: float
    peak_radius: float
    peak_value: float


@dataclass
class SsimScore:
    ssim_raw: float
    ssim_blurred: float
    blocks: list[BlockScore] = field(default_factory=list)

    @property
    def max_abs_angle_error(self) -> float | None:
        errors = [abs(b.angle_error_deg) for b in self.blocks if b.angle_error_deg is not None]
        return max(errors) if errors else None


_CENTRE = re.compile(r"\b(?:at|and)\s+(?:the\s+)?cent(?:re|er)\b", re.IGNORECASE)
_ELECTRODE = re.compile(r"(?:\be\s*|\bat\s+|\band\s+|\+\s*)(\d{1,2})\b", re.IGNORECASE)


def parse_target(text: str) -> list[str]:
    """Target text -> block labels: 'centre' and/or 'E1'..'E12'.

    Accepts the forms used on 2026-10-02: 'wood at e5', 'wood block at 10',
    'A: near E9 (block centre ~128 mm ...)', 'wood at e1 and e7',
    'wood at centre'. The phrase 'block centre' describes a measurement point,
    not a centre target, so a centre block needs 'at centre' / 'and centre'.
    """
    text = text or ""
    labels: list[str] = []
    if _CENTRE.search(text):
        labels.append("centre")
    for match in _ELECTRODE.finditer(text):
        number = int(match.group(1))
        if 1 <= number <= 12:
            label = f"E{number}"
            if label not in labels:
                labels.append(label)
    return labels


def electrode_unit_vectors(eit_mesh) -> list[tuple[float, float]]:
    """Unit vector toward each electrode, read from the mesh (E1 first)."""
    vectors = []
    for node_index in eit_mesh.el_pos:
        x, y = (float(v) for v in eit_mesh.node[node_index][:2])
        norm = float(np.hypot(x, y)) or 1.0
        vectors.append((x / norm, y / norm))
    return vectors


def blocks_for(labels: Sequence[str], eit_mesh, near_radius: float = NEAR_RADIUS_MM / TANK_RADIUS_MM) -> list[Block]:
    vectors = electrode_unit_vectors(eit_mesh)
    blocks = []
    for label in labels:
        if label == "centre":
            blocks.append(Block(label, 0.0, 0.0))
        else:
            ux, uy = vectors[int(label[1:]) - 1]
            blocks.append(Block(label, ux * near_radius, uy * near_radius))
    return blocks


def grid_coordinates(n: int = GRID) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    axis = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    xx, yy = np.meshgrid(axis, axis[::-1])  # row 0 is the top (+y)
    inside = xx**2 + yy**2 <= 1.0
    return xx, yy, inside


def rasterise(values: np.ndarray, eit_mesh, n: int = GRID) -> np.ndarray:
    """Per-element values -> n x n grid; NaN outside the mesh."""
    from matplotlib.tri import Triangulation

    nodes = np.asarray(eit_mesh.node)[:, :2]
    tri = Triangulation(nodes[:, 0], nodes[:, 1], np.asarray(eit_mesh.element))
    xx, yy, _ = grid_coordinates(n)
    index = tri.get_trifinder()(xx, yy)
    image = np.full(xx.shape, np.nan)
    hit = index >= 0
    image[hit] = np.asarray(values, dtype=float)[index[hit]]
    return image


def block_mask(blocks: Sequence[Block], n: int = GRID) -> np.ndarray:
    """Binary footprint of every block, oriented with its radial side toward the centre."""
    xx, yy, inside = grid_coordinates(n)
    half_t = BLOCK_FOOTPRINT_MM[0] / 2.0 / TANK_RADIUS_MM
    half_r = BLOCK_FOOTPRINT_MM[1] / 2.0 / TANK_RADIUS_MM
    mask = np.zeros(xx.shape)
    for block in blocks:
        if block.radius > 0:
            ur = np.array([block.x, block.y]) / block.radius
        else:
            ur = np.array([1.0, 0.0])
        ut = np.array([-ur[1], ur[0]])
        dx, dy = xx - block.x, yy - block.y
        radial = np.abs(dx * ur[0] + dy * ur[1])
        tangential = np.abs(dx * ut[0] + dy * ut[1])
        mask[(radial <= max(half_r, 0.5 / n * 2)) & (tangential <= max(half_t, 0.5 / n * 2))] = 1.0
    mask[~inside] = 0.0
    return mask


def blur(mask: np.ndarray, sigma: float = PSF_SIGMA, n: int = GRID) -> np.ndarray:
    sigma_px = sigma * n / 2.0
    out = ndimage.gaussian_filter(mask, sigma_px)
    peak = out.max()
    return out / peak if peak > 0 else out


def score_region(mask: np.ndarray, n: int = GRID) -> np.ndarray:
    """Region the ``ssim`` mean is taken over: the mask, dilated.

    Dilation is applied to the ground-truth mask alone and never to the image,
    so the region cannot follow a blob that landed somewhere else. A region
    derived from the image would let a detection in the wrong place enlarge the
    very region that judges it.
    """
    _, _, inside = grid_coordinates(n)
    return ndimage.binary_dilation(mask > 0, iterations=REGION_DILATE_PX) & inside


def resistive_image(values_grid: np.ndarray) -> np.ndarray:
    """Wood is resistive: keep the negative lobe, flip it positive, scale to [0, 1].

    The sign is the solver's (negative = conductivity decrease); a conductive
    excursion is not evidence of a wooden block and is clipped to zero.
    """
    image = np.nan_to_num(-values_grid, nan=0.0)
    image = np.clip(image, 0.0, None)
    peak = image.max()
    return image / peak if peak > 0 else image


def ssim(a: np.ndarray, b: np.ndarray, region: np.ndarray, sigma_px: float = SSIM_SIGMA_PX, data_range: float = 1.0) -> float:
    """Mean SSIM (Wang et al. 2004, Gaussian window) over ``region``."""
    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2
    f = lambda img: ndimage.gaussian_filter(img, sigma_px)  # noqa: E731
    mu_a, mu_b = f(a), f(b)
    var_a = f(a * a) - mu_a**2
    var_b = f(b * b) - mu_b**2
    cov = f(a * b) - mu_a * mu_b
    numerator = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
    denominator = (mu_a**2 + mu_b**2 + c1) * (var_a + var_b + c2)
    return float(np.mean((numerator / denominator)[region]))


def _angle_diff(a: float, b: float) -> float:
    return ((a - b + 180.0) % 360.0) - 180.0


def score_blocks(values_grid: np.ndarray, blocks: Sequence[Block], n: int = GRID) -> list[BlockScore]:
    xx, yy, inside = grid_coordinates(n)
    image = np.nan_to_num(-values_grid, nan=-np.inf)
    radius = np.hypot(xx, yy)
    angle = np.degrees(np.arctan2(yy, xx)) % 360.0
    scores = []
    for block in blocks:
        if block.label == "centre":
            region = inside & (radius <= CENTRE_SEARCH_R)
        else:
            region = inside & (np.abs(_angle_diff(angle, block.angle_deg)) <= WEDGE_DEG)
        local = np.where(region, image, -np.inf)
        flat = int(np.argmax(local))
        row, col = np.unravel_index(flat, local.shape)
        peak_angle = float(angle[row, col])
        is_centre = block.label == "centre"
        scores.append(
            BlockScore(
                label=block.label,
                true_angle_deg=None if is_centre else block.angle_deg,
                peak_angle_deg=None if is_centre else peak_angle,
                angle_error_deg=None if is_centre else _angle_diff(peak_angle, block.angle_deg),
                true_radius=block.radius,
                peak_radius=float(radius[row, col]),
                peak_value=float(-local[row, col]),
            )
        )
    return scores


def score(values: np.ndarray, eit_mesh, labels: Sequence[str], psf_sigma: float = PSF_SIGMA, n: int = GRID) -> SsimScore:
    if not labels:
        raise ValueError("no target in the run's description; nothing to build a mask from")
    blocks = blocks_for(labels, eit_mesh)
    grid = rasterise(values, eit_mesh, n)
    image = resistive_image(grid)
    mask = block_mask(blocks, n)
    region = score_region(mask, n)
    return SsimScore(
        ssim_raw=ssim(image, mask, region),
        ssim_blurred=ssim(image, blur(mask, psf_sigma, n), region),
        blocks=score_blocks(grid, blocks, n),
    )
