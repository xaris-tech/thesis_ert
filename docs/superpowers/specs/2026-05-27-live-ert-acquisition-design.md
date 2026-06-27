# Live ERT Acquisition Design

**Goal**

Turn the current ad-hoc serial visualizer into a reliable live-acquisition script for the user's 4-electrode Phase 1 setup, while shaping the output into a format that can later feed a true PyEIT reconstruction workflow.

**Context**

The existing script reads two voltage values per scan from firmware and plots baseline-vs-current differences. The hardware and firmware currently produce only a 2-value measurement vector (`E3`, `E4`) for each triggered scan, so the first version should not pretend to perform full tomography.

**Design**

- Keep a single executable entrypoint in `ert.py` so the repo stays easy to run.
- Split the code inside that file into small units:
  - serial parsing
  - scan state/baseline management
  - export formatting
  - CLI runtime loop
- Preserve the current manual workflow:
  - `s` triggers a single scan
  - `g` starts continuous scan mode
  - `x` stops continuous scan mode
  - `b` resets the baseline
  - `w` writes captured scans to disk
  - `q` exits
- Store each measurement as structured data with timestamp, channel values, and baseline deltas.
- Export scans to CSV and NumPy `.npz` so later PyEIT experiments can consume a stable measurement vector format.

**Non-Goals**

- No fake conductivity image reconstruction in this version.
- No firmware changes in this version.
- No assumptions about more than two measured voltages per scan.

**Testing**

- Add unit tests for scan parsing and export payload generation.
- Keep runtime/hardware behavior in the main script and test pure functions only.
