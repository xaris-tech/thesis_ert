from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from collections.abc import Callable

import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
from tree_ert.acquisition import Acquisition
from tree_ert.settings import UiSettings


class ControllerState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    CONFIGURED = "configured"
    BASELINE_READY = "baseline_ready"
    TARGET_READY = "target_ready"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True)
class BaselineResult:
    baseline: np.ndarray
    stability: unified.BaselineStability
    pair_scores: list[unified.PairHealthScore]
    log_path: Path | None = None

    def __len__(self) -> int:
        return len(self.baseline)


@dataclass(frozen=True)
class TargetResult:
    reconstructions: list[np.ndarray]
    frame_healths: list[unified.FrameHealthScore]
    log_path: Path | None = None


@dataclass(frozen=True)
class DriftTuneAttempt:
    settings: UiSettings
    report: unified.ControlDriftReport | None
    error: str | None = None

    @property
    def max_relative_rms_percent(self) -> float:
        if self.report is None or not self.report.frames:
            return float("inf")
        return max(frame.relative_rms_percent for frame in self.report.frames)

    @property
    def max_rms_kohm(self) -> float:
        if self.report is None or not self.report.frames:
            return float("inf")
        return max(frame.rms_kohm for frame in self.report.frames)

    @property
    def min_correlation(self) -> float:
        if self.report is None or not self.report.frames:
            return 0.0
        return min(frame.correlation for frame in self.report.frames)


@dataclass(frozen=True)
class DriftTuneResult:
    attempts: list[DriftTuneAttempt]
    best: DriftTuneAttempt | None


def drift_tuning_candidates(settings: UiSettings) -> list[UiSettings]:
    profiles = (
        (settings.settle_ms, settings.samples, settings.warmup_frames, settings.baseline_frames, settings.frames),
        (max(settings.settle_ms, 100), max(settings.samples, 16), max(settings.warmup_frames, 20), max(settings.baseline_frames, 10), max(10, min(settings.frames, 10))),
        (max(settings.settle_ms, 100), max(settings.samples, 16), max(settings.warmup_frames, 30), max(settings.baseline_frames, 15), max(10, min(settings.frames, 10))),
        (max(settings.settle_ms, 150), max(settings.samples, 16), max(settings.warmup_frames, 30), max(settings.baseline_frames, 20), max(10, min(settings.frames, 10))),
        (max(settings.settle_ms, 200), max(settings.samples, 32), max(settings.warmup_frames, 30), max(settings.baseline_frames, 20), max(10, min(settings.frames, 10))),
    )
    candidates: list[UiSettings] = []
    seen: set[tuple[int, int, int, int, int]] = set()
    for settle_ms, samples, warmup_frames, baseline_frames, frames in profiles:
        key = (settle_ms, samples, warmup_frames, baseline_frames, frames)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            replace(
                settings,
                settle_ms=settle_ms,
                samples=samples,
                warmup_frames=warmup_frames,
                baseline_frames=baseline_frames,
                frames=frames,
                # Tuning hunts for settings rather than collecting specimen data;
                # logging it would bury real ladder scans under stray CSVs.
                log_enabled=False,
            ).validate()
        )
    return candidates


class DebugController:
    def __init__(
        self,
        acquisition: Acquisition,
        progress: Callable[[str], None] | None = None,
        target_preview: Callable[[list[np.ndarray]], None] | None = None,
    ) -> None:
        self.acquisition = acquisition
        self.state = ControllerState.DISCONNECTED
        self.protocol = None
        self.solver = None
        self.mesh = None
        self.baseline_result: BaselineResult | None = None
        self._stop_requested = False
        self._progress = progress or (lambda _message: None)
        self._target_preview = target_preview or (lambda _reconstructions: None)

    def connect(self, settings: UiSettings) -> None:
        settings.validate()
        self._stop_requested = False
        self._clear_configuration()
        target = "demo acquisition" if self.acquisition.__class__.__name__ == "DemoAcquisition" else settings.port
        self._emit(f"Connecting to {target}")
        self.acquisition.connect(settings)
        self.state = ControllerState.CONNECTED
        self._emit("Connected")

    def configure(self, settings: UiSettings) -> None:
        settings.validate()
        self._stop_requested = False
        self._clear_baseline()
        self._emit(
            f"Configuring pattern={settings.pattern} "
            f"dac={settings.dac} settle={settings.settle_ms}ms samples={settings.samples}"
        )
        self.protocol, _ = unified.protocol_and_command(settings.pattern)
        self.mesh, self.solver = base.create_solver(self.protocol)
        self.acquisition.configure(settings)
        self.state = ControllerState.CONFIGURED
        self._emit("Configuration ready")

    def _open_logger(
        self,
        settings: UiSettings,
        kind: str,
        max_frames: int,
    ) -> tuple[unified.RawFrameLogger | None, str]:
        """Open a labelled CSV for this capture, or none if logging is off."""
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        if not settings.log_enabled:
            return None, run_id
        name = f"phase3a-ui-{settings.slug}-{settings.pattern}-{kind}-{run_id}.csv"
        logger = unified.RawFrameLogger(
            Path(settings.log_dir) / name,
            max_frames,
            specimen=settings.specimen.strip(),
            stage=settings.stage.strip(),
        )
        self._emit(f"Logging to {logger.path}")
        return logger, run_id

    def capture_baseline(self, settings: UiSettings) -> BaselineResult:
        self._require_configured()
        self._clear_baseline()
        vectors = []
        logger, run_id = self._open_logger(settings, "baseline", settings.baseline_frames)
        try:
            for index in range(settings.warmup_frames):
                self._raise_if_stopped()
                self._emit(f"Warmup frame {index + 1}/{settings.warmup_frames}")
                self.acquisition.capture_frame()
            for index in range(settings.baseline_frames):
                self._raise_if_stopped()
                self._emit(f"Baseline frame {index + 1}/{settings.baseline_frames}")
                frame = self.acquisition.capture_frame()
                self._raise_if_stopped()
                self._verify_pattern(frame, settings.pattern)
                if logger is not None:
                    logger.write(run_id, "baseline", frame)
                vectors.append(unified.frame_to_vector(frame, self.protocol))
        finally:
            if logger is not None:
                logger.close()
        self._emit("Checking baseline stability")
        stability = unified.require_stable_baseline(
            vectors,
            allow_unstable=settings.allow_unstable_baseline,
        )
        baseline = unified.average_vectors(vectors)
        pair_scores = unified.analyze_baseline_pair_health(vectors, self.protocol)
        result = BaselineResult(
            baseline,
            stability,
            pair_scores,
            log_path=logger.path if logger is not None else None,
        )
        self.baseline_result = result
        self.state = ControllerState.BASELINE_READY
        self._emit("Baseline ready")
        return result

    def capture_control(self, settings: UiSettings) -> unified.ControlDriftReport:
        if self.baseline_result is None:
            raise RuntimeError("baseline is required before control drift")
        controls = []
        for index in range(settings.frames):
            self._raise_if_stopped()
            self._emit(f"Control drift frame {index + 1}/{settings.frames}")
            frame = self.acquisition.capture_frame()
            self._raise_if_stopped()
            self._verify_pattern(frame, settings.pattern)
            controls.append(unified.frame_to_vector(frame, self.protocol))
        self._emit("Analyzing control drift")
        return unified.analyze_control_drift(
            self.baseline_result.baseline,
            controls,
            self.protocol,
        )

    def capture_target(self, settings: UiSettings) -> TargetResult:
        if self.baseline_result is None:
            raise RuntimeError("baseline is required before target capture")
        reconstructions = []
        healths = []
        logger, run_id = self._open_logger(settings, "target", settings.frames)
        try:
            for index in range(settings.frames):
                self._raise_if_stopped()
                self._emit(f"Target frame {index + 1}/{settings.frames}")
                frame = self.acquisition.capture_frame()
                self._raise_if_stopped()
                self._verify_pattern(frame, settings.pattern)
                if logger is not None:
                    logger.write(run_id, "target", frame)
                current = unified.frame_to_vector(frame, self.protocol)
                currents = np.asarray([abs(record.current_ua) for record in frame.records])
                filtered = unified.filter_frame_vector_best_effort(
                    baseline=self.baseline_result.baseline,
                    current=current,
                    pair_scores=self.baseline_result.pair_scores,
                    current_median_ua=float(np.median(currents)),
                    current_spread_ua=float(np.max(currents) - np.min(currents)),
                )
                reconstruction = base.reconstruct_difference(
                    self.baseline_result.baseline,
                    filtered.filtered_vector,
                    self.solver,
                )
                reconstructions.append(reconstruction)
                healths.append(filtered.frame_health)
                self._target_preview(list(reconstructions))
        finally:
            if logger is not None:
                logger.close()
        self.state = ControllerState.TARGET_READY
        self._emit("Target reconstruction ready")
        return TargetResult(
            reconstructions,
            healths,
            log_path=logger.path if logger is not None else None,
        )

    def tune_drift(self, settings: UiSettings) -> DriftTuneResult:
        settings.validate()
        attempts: list[DriftTuneAttempt] = []
        candidates = drift_tuning_candidates(settings)
        for index, candidate in enumerate(candidates, start=1):
            self._raise_if_stopped()
            self._emit(
                f"Tune attempt {index}/{len(candidates)}: "
                f"settle={candidate.settle_ms}ms samples={candidate.samples} "
                f"warmup={candidate.warmup_frames} baseline={candidate.baseline_frames} "
                f"control_frames={candidate.frames}"
            )
            try:
                self.configure(candidate)
                self.capture_baseline(candidate)
                report = self.capture_control(candidate)
            except Exception as exc:
                attempts.append(DriftTuneAttempt(candidate, None, str(exc)))
                self._emit(f"Tune attempt {index} failed: {exc}")
                continue
            attempt = DriftTuneAttempt(candidate, report)
            attempts.append(attempt)
            self._emit(
                f"Tune attempt {index} result: "
                f"max_relative={attempt.max_relative_rms_percent:.2f}% "
                f"max_rms={attempt.max_rms_kohm:.6f}kOhm "
                f"min_corr={attempt.min_correlation:.6f}"
            )
        successful = [attempt for attempt in attempts if attempt.report is not None]
        best = min(
            successful,
            key=lambda attempt: (
                attempt.max_relative_rms_percent,
                attempt.max_rms_kohm,
                -attempt.min_correlation,
            ),
            default=None,
        )
        if best is not None:
            self._emit(
                "Tune best: "
                f"settle={best.settings.settle_ms}ms samples={best.settings.samples} "
                f"warmup={best.settings.warmup_frames} baseline={best.settings.baseline_frames} "
                f"control_frames={best.settings.frames} "
                f"max_relative={best.max_relative_rms_percent:.2f}% "
                f"min_corr={best.min_correlation:.6f}"
            )
        else:
            self._emit("Tune failed: no successful drift attempts")
        return DriftTuneResult(attempts, best)

    def stop(self) -> None:
        self._stop_requested = True
        self._emit("STOP requested")
        self.acquisition.stop()
        self.state = ControllerState.STOPPED

    def close(self) -> None:
        try:
            self.acquisition.close()
        finally:
            self._stop_requested = False
            self._clear_configuration()
            self.state = ControllerState.DISCONNECTED

    def _require_configured(self) -> None:
        if self.state not in {
            ControllerState.CONFIGURED,
            ControllerState.BASELINE_READY,
            ControllerState.TARGET_READY,
        } or self.protocol is None or self.solver is None:
            raise RuntimeError("configure before capture")

    def _raise_if_stopped(self) -> None:
        if self._stop_requested:
            raise RuntimeError("capture stopped")

    def _clear_baseline(self) -> None:
        self.baseline_result = None

    def _clear_configuration(self) -> None:
        self.protocol = None
        self.solver = None
        self.mesh = None
        self._clear_baseline()

    def _emit(self, message: str) -> None:
        self._progress(message)

    @staticmethod
    def _verify_pattern(frame: unified.UnifiedFrame, expected: str) -> None:
        if frame.pattern != expected:
            raise ValueError(f"Firmware returned {frame.pattern}, expected {expected}")
