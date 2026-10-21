# ADR-0069: Build the FEM mesh once per process and pick the serial port default by OS

- **Status:** Accepted
- **Date:** 2026-10-21
- **Affects:** `phase3a_reconstruct.create_solver`, `DEFAULT_PORT`, `tree_ert/settings.py`, `tree_ert_app.py`, `tree_ert/ui.py`
- **Related:** `docs/repo-changes-needed.md` §1.1 and §3, ADR-0041

## Context

The host is moving to a Raspberry Pi 5. Profiling one recorded run on the desktop
(`20261021-124349-disc-02-*`, 4 frames, absolute + split-half) took 5.2 s, of which 1.5 s was
`create_solver` rebuilding the same distmesh three times (0.4 s each). Every caller of
`create_solver` (absolute solve, split-half, difference, save, self-test) rebuilds it. On a Pi
this is roughly 3-4x slower. Capture itself is firmware-bound (`docs/repo-changes-needed.md` §3:
~28 s/frame at settle 30, n 16) and the host does not limit it.

The serial default `COM3` was repeated as a literal in six places and does not exist on Linux,
where the native-USB ESP32-S3 enumerates as `/dev/ttyACM0`.

## Decision

`create_solver` builds the mesh once per process (`_template_mesh`, `lru_cache`) and hands each
caller a `deepcopy`; the JAC solver is still set up per call. `phase3a_reconstruct.DEFAULT_PORT`
is `COM3` on Windows and `/dev/ttyACM0` elsewhere, and the other entry points import it.

## Rationale

The mesh depends only on constants (`n_el=12`, `h0=0.12`), and distmesh is deterministic: two
builds, one after reseeding NumPy's RNG, give identical nodes and elements (476 elements). So
caching cannot change any image, vector or gate result. Measurement settings, averaging, gates
and solver parameters are untouched, so data quality is unchanged.

Rejected: caching the whole `(mesh, JAC)` pair (saves another ~0.1 s, but the solver object would
be shared state across threads in the Qt worker); lowering mesh resolution or GN iterations (faster,
but changes what an image means); changing firmware timing (`delay(1)` per conversion) — that is
the real capture-time lever but changes the measurement and needs bench evidence first.

## Consequences

Absolute + split-half costs ~1 s less per run on the desktop, more on the Pi. A future change to
`mesh.create` arguments must stay inside `_template_mesh`. The port default is only a default;
a USB-UART bridge (`/dev/ttyUSB0`) or a second board still needs `--port`.

## Verification

`python -m unittest discover -s tests` passes. Determinism check: build the mesh twice with
different RNG seeds and compare `node`/`element` with `np.array_equal`.
