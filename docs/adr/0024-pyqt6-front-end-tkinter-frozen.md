# ADR-0024: PyQt6 session-driver front-end; Tkinter is frozen, not removed

- **Status:** Accepted
- **Date:** 2026-09-11
- **Affects:** `tree_ert/qt/`, `tree_ert/capture_view.py`, `tree_ert_qt.py`, `tree_ert/ui.py`
  (frozen), the deployment target for field capture
- **Related:** consumes [ADR-0023](0023-per-run-folders-with-a-conditions-sheet.md); serves the
  sessions defined by [ADR-0021](0021-saline-tank-as-the-deferred-phantom.md) and
  [ADR-0022](0022-titrate-the-medium-with-the-instrument.md)
- **Evidence:** `tests/test_tree_ert_qt.py` (21 tests), `tests/test_capture_view.py` (33 tests)

## Context

The debug UI is Tkinter (`tree_ert/ui.py`) and in practice Windows-bound. The instrument is meant
to be carried to trees, and the intended field host is a Raspberry Pi with a small display — a
platform where Tkinter is workable but unpleasant, and where the existing layout, built for
bench debugging, does not fit.

The immediate need is narrower than "a better UI". ADR-0022 titrates the tank during a session:
many short captures, each at a different concentration, each needing its own metadata recorded
before the data is worth keeping. ADR-0023 provides the storage for that but nothing yet drives
it. The operator's decision was to build the UI before the first capture session rather than
drive it from the CLI.

The existing layering is favourable. `UiSettings`, the `Acquisition` protocol and
`DebugController` are all independent of Tkinter, so a second front-end is additive rather than
a rewrite.

## Decision

A PyQt6 front-end is added as a **session driver**: port selection, instrument settings, a
conditions form, capture into a run folder, a live raw-value table with quality flags, and live
reciprocity and noise-floor readouts. There is no reconstruction view in this version.

`tree_ert/ui.py` (Tkinter) is **frozen**: it remains runnable and receives bug fixes only. All new
UI work goes to Qt. It is not deleted.

The binding is **PyQt6**, installed by pip on Windows and by `apt install python3-pyqt6` on
Raspberry Pi OS. The code is written to be platform-clean from the start: ports are enumerated
through `serial.tools.list_ports`, no `COM` naming is assumed, and paths go through `pathlib`.

Presentation logic lives in `tree_ert/capture_view.py`, which imports no UI toolkit.

## Rationale

**Why PyQt6 over PySide6.** PySide6 is the official binding and its LGPL licence is friendlier
than PyQt's GPL. It was rejected on deployment risk: ARM64 wheel availability is the weak point,
and `pip install PySide6` on a Raspberry Pi is liable to need a source build. PyQt6 ships as a
prebuilt Debian ARM package. The licence difference does not bind a thesis project. The cost is
that a Pi venv must be created with `--system-site-packages` to see the apt-installed package.

**Why PyQt6 over PyQt5.** Qt5 is in extended maintenance. Starting new work on it means starting
on a sunsetting stack for no benefit, since both are equally available on the Pi.

**Why no reconstruction view in v1.** During titration the image is the least informative thing
on screen: the medium is homogeneous by design, so there is nothing to reconstruct, and the
decisions being made — is the medium in the instrument's window, are pairs flagged, is
reciprocity moving — are all scalar. Feature parity with the Tkinter UI was considered and
rejected as porting screens this session will not use.

**Why freeze Tkinter rather than delete or maintain it.** Deleting it leaves no working UI until
Qt reaches parity, immediately before a capture session. Maintaining both invites divergence and
double work. Freezing keeps a known-good fallback at near-zero cost, at the price of the repo
carrying two UIs for a while.

**Why a separate `capture_view` module.** Widget code is awkward to test and tends to accumulate
logic that then cannot be reused. Putting every computed number in a toolkit-free module keeps
the tested surface large and the untested surface thin, and matches the pattern
`tree_ert/selftest.py` already established: pure functions over already-collected evidence. The
Tkinter UI and the CLI can adopt it unchanged.

**Why capture runs on a worker thread.** A 12-electrode adjacent sweep with settle time and
sample averaging blocks for seconds. On the event loop that freezes the window, and a frozen
window is indistinguishable from a hung instrument — the moment an operator reaches for the
reset button. Cancellation is cooperative, checked between frames: a thread killed mid-frame
leaves a partial record in the serial buffer, and the next session then reads a frame that begins
in the middle of the last one.

**Known imperfections.** Incomplete conditions produce a confirmation dialog rather than a block,
so an operator in a hurry can still record a run with unmeasured fields — mitigated only by the
gaps being listed in the run itself. The window has no reconstruction, no self-test tab and no
baseline/target workflow, so the Tkinter UI is still required for those. And nothing has yet been
run on an actual Raspberry Pi.

## Consequences

**Easier.** The titration session has a driver that cannot write a run without also writing its
conditions. Linux and the Pi become viable hosts. Presentation logic is now testable, which it
was not inside Tkinter callbacks.

**Harder.** Two UIs exist, and a change to the shared controller layer must be checked against
both. PyQt6 is a new and substantial dependency — around 100 MB installed — and on the Pi it must
come from apt, which constrains how the venv is created. Qt's threading model adds a failure mode
the Tkinter UI did not have.

**Committed to.** New UI work goes to Qt. `capture_view` is now the place presentation numbers
live, and putting them back into widget code would undo the testability this ADR is justified by.
The Pi deployment path is committed to apt-provided Qt.

**Will bite later.** The Pi has never been tested; PyEIT mesh construction and JAC solving on ARM
may be slow enough to force the reconstruction view into a different shape than the desktop one,
which is an argument discovered only after the hardware arrives. Freezing Tkinter tends toward
neglect rather than a decision: the realistic end state is that it rots until someone deletes it,
and this ADR does not set the date.

## Verification

- `tests/test_tree_ert_qt.py` — 21 tests, offscreen (`QT_QPA_PLATFORM=offscreen`), skipped
  cleanly when PyQt6 is absent. Covers an end-to-end demo capture through the worker:
  - `test_demo_capture_writes_a_complete_run` — conditions, frames, summary all written
  - `test_every_frame_reaches_the_csv_unaveraged` — ADR-0023's retention rule holds through the UI
  - `test_warmup_frames_are_reported_but_not_recorded` — discarded frames stay discarded
  - `test_cancel_keeps_the_frames_already_captured` — a stopped run is still data
  - `test_a_failure_mid_capture_still_leaves_the_run_readable` — a mid-capture serial failure
    leaves both frames captured so far and the conditions readable
  - `test_unexposed_settings_keep_their_stored_values` — a setting not on screen is not reset
- `tests/test_capture_view.py` — 33 tests, no Qt, no hardware.
- Full suite: 294 tests passing.
- Manual: `python tree_ert_qt.py --demo` renders and captures with no hardware attached.

**Not verified:** nothing in this ADR has been run on a Raspberry Pi, on Linux, or against real
hardware through the Qt path. The apt/`--system-site-packages` instructions are from
documentation, not from a performed install. Falsified the first time either fails on the Pi.
