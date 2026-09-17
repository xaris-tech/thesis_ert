"""Background capture worker.

Serial capture blocks for as long as a frame takes to scan -- on a 12-electrode
adjacent sweep with settle time and sample averaging, comfortably seconds. Doing
that on the Qt event loop freezes the window, and a frozen window during a
titration step is indistinguishable from a hung instrument, which is the moment
an operator reaches for the reset button.

So the whole session runs on a worker thread and reports back by signal. The
worker owns the :class:`~tree_ert.acquisition.Acquisition` and the
:class:`~run_record.RunRecorder`; the window owns neither and only renders what
it is handed. Nothing here imports a widget.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

import run_record
from run_record import Conditions
from tree_ert import capture_view, reconstruction
from tree_ert.acquisition import Acquisition
from tree_ert.settings import UiSettings, settings_to_dict


@dataclass(frozen=True)
class SessionBaseline:
    """The run every later capture in this session is differenced against.

    Frames are held in memory rather than re-read from disk: the baseline is by
    definition from this session, and re-parsing its CSV would reconstruct the
    vectors from a lossier source than the objects already in hand.
    """

    run_id: str
    frames: list
    settings: dict


@dataclass(frozen=True)
class CaptureRequest:
    """Everything one capture session needs, assembled before the thread starts.

    Passed as a frozen value rather than read from widgets on the worker thread,
    so a setting the operator edits mid-capture cannot change the run underneath
    itself -- the recorded conditions would then describe a run that never
    happened.
    """

    settings: UiSettings
    conditions: Conditions
    label: str
    frames: int
    warmup_frames: int
    baseline: "SessionBaseline | None" = None
    """None means this run becomes the session baseline and has no image of its
    own -- which is correct, not a gap: a baseline has nothing to differ from."""
    override_reciprocity: bool = False
    """Reconstruct even when the reciprocity gate fails (ADR-0030). The image
    is then stamped OVERRIDDEN in its figure, text file and index row."""


class CaptureWorker(QObject):
    """Runs one capture session: connect, configure, warm up, capture, record.

    Signals carry plain data and already-formatted strings. The worker does the
    summarising because the summaries are cheap and doing them here keeps the
    per-frame work off the event loop entirely.
    """

    started = pyqtSignal(str)
    """Run id, emitted once the run directory exists."""

    progress = pyqtSignal(str)
    """Human-readable status for the log pane."""

    frame_captured = pyqtSignal(object, int, str)
    """(UnifiedFrame, zero-based frame index, formatted per-frame summary)."""

    warmup_frame = pyqtSignal(int, int, str)
    """(completed, total, formatted summary) for frames that are discarded."""

    finished = pyqtSignal(str, str)
    """(run directory as text, formatted session summary)."""

    failed = pyqtSignal(str)
    """Message. Emitted instead of finished; the run directory is kept either way."""

    reconstructed = pyqtSignal(str, object, object)
    """(image path, ReconstructionResult, control result or None) once the
    difference image is written. The control is the baseline against itself and
    is what makes the image readable; None means the baseline was too short to
    split, and the image then has nothing to be compared against."""

    reconstruction_skipped = pyqtSignal(str)
    """Why no image was produced. Always emitted when one was not, so the
    absence of an image is never silent."""

    def __init__(
        self,
        acquisition: Acquisition,
        request: CaptureRequest,
        log_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._acquisition = acquisition
        self._request = request
        self._log_dir = Path(log_dir or request.settings.log_dir)
        self._cancel = threading.Event()
        self._last_control = None
        """Control image from the most recent reconstruction, for the index."""
        self._reciprocity_gate = ""
        """pass / fail / overridden once a reconstruction was attempted; empty
        for a baseline, which is never gated (ADR-0030)."""
        self._captured: list = []
        """Frames recorded so far. Kept on the worker so a failure part-way
        through can still index what was captured before it."""

    def cancel(self) -> None:
        """Ask the session to stop after the frame in flight.

        Cooperative rather than forced: a thread killed mid-frame leaves the
        serial port holding a partial record, and the next session then reads a
        frame that starts in the middle of the last one.
        """
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def run(self) -> None:
        """Entry point for the worker thread. Never raises into Qt."""
        recorder = None
        try:
            settings = self._request.settings.validate()

            self.progress.emit(f"Connecting to {settings.port}...")
            self._acquisition.connect(settings)
            self.progress.emit("Configuring instrument...")
            self._acquisition.configure(settings)

            recorder = run_record.create_run(
                self._log_dir,
                self._request.label,
                conditions=self._request.conditions,
                settings=settings_to_dict(settings),
            )
            self.started.emit(recorder.run_id)
            self.progress.emit(f"Recording to {recorder.path}")

            self._warm_up(self._request.warmup_frames)
            frames = self._capture(recorder, self._request.frames)

            summary = capture_view.session_summary(frames)
            summary_text = capture_view.format_session_summary(summary)
            recorder.write_text("summary.txt", summary_text + "\n")
            image = self._reconstruct(recorder, frames, settings, summary)
            self._index(
                recorder,
                "cancelled" if self._cancel.is_set() else "complete",
                summary,
                image,
            )
            self.finished.emit(str(recorder.path), summary_text)
        except Exception as exc:  # noqa: BLE001 - a worker must not raise into Qt
            # A failed run is still a scan that happened, and the index is the
            # only place a later reader would see that it did. Indexing it is
            # best-effort: a second failure here must not replace the first.
            if recorder is not None:
                try:
                    self._index(
                        recorder,
                        "failed",
                        capture_view.session_summary(self._captured),
                    )
                except Exception:  # noqa: BLE001
                    pass
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if recorder is not None:
                recorder.close()
            try:
                self._acquisition.stop()
            except Exception:  # noqa: BLE001 - already failing; do not mask why
                pass

    # -- internals -------------------------------------------------------

    def _warm_up(self, count: int) -> None:
        """Capture and discard frames while the electrode double layer settles.

        Discarded frames are still summarised to the log. They are the operator's
        only view of whether the instrument is settling or simply broken, and a
        session that warms up for ten frames in silence hides a fault for a
        minute of otherwise wasted time.
        """
        for index in range(count):
            if self._cancel.is_set():
                return
            frame = self._acquisition.capture_frame()
            text = capture_view.format_frame_summary(capture_view.frame_summary(frame))
            self.warmup_frame.emit(index + 1, count, text)

    def _reconstruct(
        self,
        recorder: run_record.RunRecorder,
        frames: list,
        settings: UiSettings,
        summary,
    ):
        """Difference this run against the session baseline, if there is one.

        Failure here never fails the capture: the frames are already on disk and
        a reconstruction can be redone from them, so a solver or settings
        problem costs an image, not a run. Every path emits something, so an
        absent image always has a stated reason.
        """
        baseline = self._request.baseline
        if baseline is None:
            self.reconstruction_skipped.emit(
                "This run is the session baseline; it has nothing to differ from."
            )
            self._save_baseline_control(recorder, frames, settings, summary)
            return None
        if not frames:
            self.reconstruction_skipped.emit("No frames were captured.")
            return None
        failures = [
            f"{name}: {reason}"
            for name, reason in (
                ("baseline", reconstruction.reciprocity_gate(baseline.frames)),
                ("this run", reconstruction.reciprocity_gate(frames)),
            )
            if reason
        ]
        override_note = ""
        if failures:
            detail = "; ".join(failures)
            if not self._request.override_reciprocity:
                self._reciprocity_gate = "fail"
                self.reconstruction_skipped.emit(
                    f"Reciprocity check failed, so no image was made ({detail}). "
                    "Frames are saved. Fix reciprocity first, or tick the override "
                    "to image anyway."
                )
                return None
            self._reciprocity_gate = "overridden"
            override_note = f"RECIPROCITY OVERRIDDEN - NOT VALID DATA ({detail})"
            self.progress.emit(override_note)
        else:
            self._reciprocity_gate = "pass"
        try:
            noise = summary.noise
            result = reconstruction.reconstruct(
                baseline.frames,
                frames,
                settings,
                baseline_settings=baseline.settings,
                target_settings=settings_to_dict(settings),
                noise_floor_kohm=noise.median_pair_std_kohm if noise else None,
            )
            # The baseline against itself: what noise looks like through this
            # solver, in the same units as the image beside it. Without it a
            # drift image and a real feature are indistinguishable, because
            # both auto-scale to fill the colour range.
            control = reconstruction.split_half_control(
                baseline.frames,
                settings,
                noise_floor_kohm=noise.median_pair_std_kohm if noise else None,
            )
            if control is None:
                self.progress.emit(
                    "Baseline has fewer than 4 frames, so no control image "
                    "could be made; the reconstruction has nothing to be "
                    "compared against."
                )

            image_path, _ = reconstruction.save_reconstruction(
                result,
                settings,
                recorder.path / "reconstruction.png",
                recorder.path / "reconstruction.npz",
                title=f"{recorder.label} vs baseline",
                subtitle="\n".join(
                    line for line in (override_note, f"baseline: {baseline.run_id}") if line
                ),
                control=control,
            )
            caption = reconstruction._magnitude_caption(result)
            if control is not None:
                caption += (
                    f"\ncontrol peak {control.peak_value:+.3e}"
                    f"\nsignificance {reconstruction.significance(result, control):.2f}x"
                    " the noise image"
                )
            if override_note:
                caption = f"{override_note}\n{caption}"
            recorder.write_text(
                "reconstruction.txt", caption + f"\nbaseline run: {baseline.run_id}\n"
            )
            self.reconstructed.emit(str(image_path), result, control)
            self._last_control = control
            return result
        except reconstruction.SettingsMismatch as exc:
            self.reconstruction_skipped.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - an image must not fail a capture
            self.reconstruction_skipped.emit(
                f"Reconstruction failed: {type(exc).__name__}: {exc}"
            )
        return None

    def _save_baseline_control(
        self,
        recorder: run_record.RunRecorder,
        frames: list,
        settings: UiSettings,
        summary,
    ) -> None:
        """Save the baseline's image of itself into its own run folder (ADR-0029).

        A baseline has no difference image, but it does have a noise image: its
        first half against its second. Saved as ``control.*``, never as
        ``reconstruction.*``, so no reader can mistake it for a detection. The
        same image is redrawn beside every later run; this copy exists so the
        baseline folder shows how quiet the reference was on its own.
        """
        noise = summary.noise
        try:
            control = reconstruction.split_half_control(
                frames,
                settings,
                noise_floor_kohm=noise.median_pair_std_kohm if noise else None,
            )
            if control is None:
                self.progress.emit(
                    "Baseline has fewer than 4 frames, so no control image was saved."
                )
                return
            image_path, _ = reconstruction.save_reconstruction(
                control,
                settings,
                recorder.path / "control.png",
                recorder.path / "control.npz",
                title=(
                    f"{recorder.label}: baseline against itself\n"
                    "(noise only - not a reconstruction)"
                ),
                subtitle="first half of frames vs second half; nothing changed",
            )
            recorder.write_text(
                "control.txt",
                reconstruction._magnitude_caption(control)
                + "\nbaseline against itself: this is noise, not a detection\n",
            )
            self.progress.emit(f"Baseline control image saved to {image_path}")
        except Exception as exc:  # noqa: BLE001 - an image must not fail a capture
            self.progress.emit(
                f"Baseline control image failed: {type(exc).__name__}: {exc}"
            )

    def _index(
        self, recorder: run_record.RunRecorder, outcome: str, summary, image=None
    ) -> None:
        """Append this run to the scans index (ADR-0025)."""
        reciprocity = summary.reciprocity
        noise = summary.noise
        baseline = self._request.baseline
        run_record.append_index_row(
            self._log_dir,
            recorder.index_row(
                outcome=outcome,
                baseline_run=baseline.run_id if baseline else "",
                peak_value=image.peak_value if image else None,
                peak_angle_deg=image.peak_angle_deg if image else None,
                control_peak=(
                    self._last_control.peak_value if self._last_control else None
                ),
                reciprocity_gate=self._reciprocity_gate,
                significance=(
                    reconstruction.significance(image, self._last_control)
                    if image is not None and self._last_control is not None
                    else None
                ),
                reciprocity_median_percent=(
                    reciprocity.median_error_percent if reciprocity else None
                ),
                reciprocity_max_percent=(
                    reciprocity.max_error_percent if reciprocity else None
                ),
                reciprocity_sign_flips=(
                    reciprocity.sign_flip_count if reciprocity else None
                ),
                reciprocity_pairs=reciprocity.pair_count if reciprocity else None,
                noise_median_kohm=noise.median_pair_std_kohm if noise else None,
                noise_median_percent=(
                    noise.median_pair_relative_percent if noise else None
                ),
            ),
        )

    def _capture(self, recorder: run_record.RunRecorder, count: int) -> list:
        frames = self._captured
        for _ in range(count):
            if self._cancel.is_set():
                self.progress.emit(
                    f"Cancelled after {len(frames)} frame(s); the run is kept."
                )
                break
            frame = self._acquisition.capture_frame()
            index = recorder.write_frame(frame)
            frames.append(frame)
            text = capture_view.format_frame_summary(capture_view.frame_summary(frame))
            self.frame_captured.emit(frame, index, text)
        return frames


def available_ports() -> list[tuple[str, str]]:
    """(device, description) for each serial port, cross-platform.

    Uses pyserial's own enumeration rather than globbing ``COM*`` or
    ``/dev/tty*``: the Raspberry Pi is the deployment target (ADR-0024) and the
    device naming there shares nothing with Windows.
    """
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    ports = []
    for port in list_ports.comports():
        ports.append((port.device, port.description or port.device))
    return sorted(ports)
