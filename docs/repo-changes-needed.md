# Changes the repo needs (review of 2026-10-20)

Review findings from a session run on the Raspberry Pi 5 (aarch64, Raspberry Pi OS,
Python 3.13). Nothing here is implemented yet. Each item says what is wrong, where,
and what the change should be. Items that change what an image means need an ADR
when they are implemented (see `CLAUDE.md`).

## 1. Raspberry Pi / Linux portability

The whole project runs on the Pi. The full suite passed there (528 tests before the
merge of `new`), including the Qt UI under `QT_QPA_PLATFORM=offscreen` and the
firmware compile tests once `arduino-cli` was installed. What does not fit is the
Windows-only defaults and instructions.

### 1.1 Serial port defaults are Windows names

`COM3` is the default in:

| File | Line |
|---|---|
| `tree_ert/settings.py` | `port: str = "COM3"` |
| `tree_ert_app.py` | `--port` default |
| `tree_ert/ui.py` | `run_app(..., port="COM3")` |
| `phase3a_reconstruct.py` | `DEFAULT_PORT` |
| `phase3a_unified_reconstruct.py` | `DEFAULT_PORT` |
| `ert.py` | `DEFAULT_PORT` (deprecated tool) |

On Linux the board appears as `/dev/ttyACM0` (native USB) or `/dev/ttyUSB0`
(USB-UART bridge). Change: one default in `tree_ert/settings.py` chosen by platform
(`COM3` on Windows, `/dev/ttyACM0` elsewhere), imported by the other entry points
instead of each repeating a literal. Better still, list ports with
`serial.tools.list_ports` in the Qt settings panel. Until then, pass `--port`.

### 1.2 `firmware_compile.py` only searches Windows install paths

`CANDIDATE_CLI_PATHS` names only the Arduino IDE's bundled `arduino-cli.exe`. It
already checks `ARDUINO_CLI` and `shutil.which("arduino-cli")` first, so it works on
the Pi once `arduino-cli` is on `PATH`. Change: document that in ADR-0016's
successor or the setup section below; no code change is strictly needed.

### 1.3 Documentation commands are Windows-only

`.\.venv\Scripts\python.exe` appears in `CLAUDE.md`, `AGENTS.md`, `HANDOVER.md`,
`docs/validity-audit.md`, `docs/verification-protocol.md`,
`docs/current-setup-validation-runbook.md`, `docs/handoff-2026-10-07.md`,
`ssim/saline-tank-2026-10-02/NEXT-STEPS.md` and ADRs 0015, 0016 and 0038. On the Pi
the interpreter is `.venv/bin/python`. Change: give both forms once in `CLAUDE.md`
and the setup section, not in every document. Accepted ADRs stay as written.

### 1.4 `ert.py` keyboard input uses `msvcrt`

Windows-only, but guarded, so it does not crash on Linux. The tool is deprecated;
leave it.

### 1.5 Paths in recorded data use backslashes

`scans/session.log` records paths like `scans\runs\<id>`. Readers that parse those
lines (for example the frame-timing analysis below) must accept both separators.
Check `run_record.py` writes paths with `Path.as_posix()` or `os.sep` consistently.

## 2. Setup on the Pi

There is no Pi setup guide. These are the commands that worked:

```bash
sudo apt install -y python3-venv python3-tk python3-pyqt6 git gh
sudo usermod -aG dialout $USER            # serial access; log out and in
python3 -m venv --system-site-packages .venv   # system PyQt6, no ARM64 wheel
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v   # ~9 min on a Pi 5

# Optional: firmware compile test and flashing
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR=$HOME/.local/bin sh
arduino-cli config init
arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32
arduino-cli lib install "Adafruit ADS1X15" "Adafruit MCP4725"
```

Change: put this in `README` or `docs/raspberry-pi-setup.md` and link it from
`CLAUDE.md`. `requirements.txt` already notes the apt route for PyQt6.

## 3. Capture time

Measured from 1,700+ frames in `scans/session.log` and confirmed against the
firmware timing loop. Per measurement:

    t_meas ~= 2 ms + settle + 6.1 ms x n        (n = samples per reading)

Each reading takes `n` current conversions plus `1 + n` voltage conversions at
860 SPS (~1.2 ms each), with `delay(1)` and I2C overhead per conversion.

| Pattern (meas/frame) | settle ms | n | Frame, logged | Frame, model |
|---|---:|---:|---:|---:|
| adjacent (216) | 10 | 8 | 14 s | 13 s |
| adjacent (216) | 30 | 16 | 28 s | 28 s |
| adjacent (216) | 30 | 32 | 49 s | 49 s |
| adjacent (216) | 100 | 32 | 64 s | 64 s |
| opposite / skip-2 (192) | 30 | 32 | 44 s | 44 s |

With the saved UI settings (adjacent, settle 30, n16, 10 warmup + 5 baseline,
5 + 5 per target) a baseline run is ~7 min and each target run ~4.7 min. The
ADS1115 alone sets a floor of ~7 s per frame at settle 0. The recalibration ladder
can add an hour, because each attempt is a whole run.

Change: `docs/planned-improvements.md` quotes "15-20 seconds" per frame at n16; the
measured figure is 28 s at settle 30. Show an estimated run duration in the Qt start
dialog from this formula (a `capture_view` function, so it is testable). The
`delay(1)` after each conversion costs ~1 ms of the 6.1 ms per sample and is worth
reviewing in firmware: the ADS1115 conversion already blocks until ready.

## 4. GREIT as an alternative difference solver

GREIT is not used anywhere in the repo. Every difference image comes from
`phase3a_reconstruct.create_solver`: one-step `JAC` with
`p=0.45, lamb=0.01, method="kotre"`.

It was compared offline on `ssim/saline-tank-2026-10-02` (19 targets, each against
its own baseline, scored by the existing `tree_ert/ssim.py` and significance code,
before the merge of `new`). GREIT's grid-space `H` was mapped to per-element rows
by nearest pixel, and the same frame scaling as `JAC.solve_gs` was used, so nothing
downstream changed.

| Solver | SSIM raw | SSIM blurred | Max angle error, median | Radius error | Significance, median |
|---|---:|---:|---:|---:|---:|
| JAC (current) | 0.438 | 0.458 | 5.0 deg | 0.34 | 11.0 |
| GREIT lamb 1e-2 | 0.449 | 0.552 | 6.4 deg | 0.13 | 14.3 |
| GREIT lamb 1e-3 | 0.446 | 0.530 | 3.3 deg | 0.21 | 12.1 |
| GREIT lamb 1e-1 | 0.448 | 0.547 | 8.1 deg | 0.10 | 12.7 |

Radius error is |peak radius - true radius| in tank radii.

- GREIT puts blocks at the right depth (radius error 0.34 to 0.13) and lifts blurred
  SSIM ~20 % and significance ~30 % on single-block targets.
- Angle accuracy is no better except at lamb 1e-3.
- The centre target drops from significance 5.8 to 1.9 at default GREIT, under the
  2.0 gate. That must be understood before GREIT is trusted.
- GREIT is difference-only; it does not help `tree_ert/absolute.py`.

Change, if adopted: add GREIT (lamb 1e-3) as a second solver selectable in
`create_solver`, keep JAC as the default, report both in `ssim_eval.py`, and write
an ADR — this changes what an image means. Re-run the comparison on the newer saline
position series (2026-10-14) first. The comparison script was not committed; it is
reproducible from the description above.

## 5. Git and branches

- `new` was merged into `main` locally on 2026-10-20 (clean, no conflicts), not
  pushed.
- `ssim` is fully contained in `new`; `absolute-reconstruction-disc-series` is fully
  contained in `main`. Both can be deleted on the remote.
- `ranjo-branch` has 3 commits not on `main` and is 53 behind, last touched
  2026-08-12. Review and either merge or archive it with a tag, as was done for
  `codex/phase3a-debug-ui`.

## 6. Fixed during this review

- `requirements.txt` lacked `pillow`. The Tkinter UI embeds matplotlib figures, and
  matplotlib's Tk backend imports `PIL.ImageTk`.
  On the Pi the system `python3-pil` has no `ImageTk`, so 15 Tkinter UI tests
  errored. Added `pillow`; in a `--system-site-packages` venv install it with
  `pip install --ignore-installed pillow` (or `sudo apt install python3-pil.imagetk`).
- `tests/test_absolute.py::test_stops_after_repeated_contact_faults` stubbed
  `contact_fault` with one argument after `new` changed it to take the excluded
  electrodes too. The stub now accepts both.

## 7. Implemented on branch `rpi` (not on `new`)

ADR-0069, kept off `new` until the Pi is in use: the FEM mesh is built once per process and
copied per caller (distmesh is deterministic, so images are unchanged; ~1 s less per run on
the desktop), and `DEFAULT_PORT` is `COM3` on Windows, `/dev/ttyACM0` elsewhere, imported by
the other entry points (§1.1). Merge `rpi` when moving to the Pi.
