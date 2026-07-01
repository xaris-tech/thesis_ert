from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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

    def __len__(self) -> int:
        return len(self.baseline)


@dataclass(frozen=True)
class TargetResult:
    reconstructions: list[np.ndarray]
    frame_healths: list[unified.FrameHealthScore]


class DebugController:
    def __init__(self, acquisition: Acquisition, progress: Callable[[str], None] | None = None) -> None:
        self.acquisition = acquisition
        self.state = ControllerState.DISCONNECTED
        self.protocol = None
        self.solver = None
        self.mesh = None
        self.baseline_result: BaselineResult | None = None
        self._stop_requested = False
        self._progress = progress or (lambda _message: None)

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

    def capture_baseline(self, settings: UiSettings) -> BaselineResult:
        self._require_configured()
        self._clear_baseline()
        vectors = []
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
            vectors.append(unified.frame_to_vector(frame, self.protocol))
        self._emit("Checking baseline stability")
        stability = unified.require_stable_baseline(
            vectors,
            allow_unstable=settings.allow_unstable_baseline,
        )
        baseline = unified.average_vectors(vectors)
        pair_scores = unified.analyze_baseline_pair_health(vectors, self.protocol)
        result = BaselineResult(baseline, stability, pair_scores)
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
        for index in range(settings.frames):
            self._raise_if_stopped()
            self._emit(f"Target frame {index + 1}/{settings.frames}")
            frame = self.acquisition.capture_frame()
            self._raise_if_stopped()
            self._verify_pattern(frame, settings.pattern)
            current = unified.frame_to_vector(frame, self.protocol)
            currents = np.asarray([abs(record.current_ua) for record in frame.records])
            filtered = unified.filter_frame_vector_best_effort(
                baseline=self.baseline_result.baseline,
                current=current,
                pair_scores=self.baseline_result.pair_scores,
                current_median_ua=float(np.median(currents)),
                current_spread_ua=float(np.max(currents) - np.min(currents)),
            )
            reconstructions.append(
                base.reconstruct_difference(
                    self.baseline_result.baseline,
                    filtered.filtered_vector,
                    self.solver,
                )
            )
            healths.append(filtered.frame_health)
        self.state = ControllerState.TARGET_READY
        self._emit("Target reconstruction ready")
        return TargetResult(reconstructions, healths)

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
