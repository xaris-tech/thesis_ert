from __future__ import annotations

import time
from dataclasses import dataclass, replace
from enum import Enum
from collections.abc import Callable

import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
from tree_ert import selftest
from tree_ert.acquisition import Acquisition
from tree_ert.settings import UiSettings


class CaptureStopped(RuntimeError):
    """Raised when STOP interrupts a capture, carrying whatever was collected.

    Subclasses RuntimeError so existing callers that catch RuntimeError keep
    working; `partial` lets a caller keep the frames captured before the stop
    instead of discarding several minutes of work.
    """

    def __init__(self, message: str = "capture stopped", partial: object = None) -> None:
        super().__init__(message)
        self.partial = partial


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


@dataclass(frozen=True)
class FrameDiagnostics:
    """One-frame screen: current margin plus the two dominant saline faults."""

    frame: unified.UnifiedFrame
    probe: unified.FrameProbe
    polarization: unified.PolarizationReport
    offset: unified.OffsetReport
    electrodes: list[unified.ElectrodeHealth]


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
        self._select_dac_address()
        self._emit("Connected")

    def _select_dac_address(self) -> None:
        """Bind the firmware's DAC driver to whatever the I2C scan reports.

        Advisory, never fatal: the firmware already picks an address at boot, so
        a failure here costs a correction, not the session. The outcome is
        emitted either way because a DAC on an unexpected address is worth
        seeing in the log next to the run it produced.
        """
        try:
            result = self.acquisition.select_dac_address()
        except Exception as exc:  # noqa: BLE001 - advisory step, never fatal
            self._emit(f"DAC address check skipped: {exc}")
            return
        self._emit(
            f"DAC address: {result.detail}" if result.resolved
            else f"DAC address unresolved: {result.detail}"
        )

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

    def probe_frame(self, settings: UiSettings) -> FrameDiagnostics:
        """Capture one frame and screen it without warmup or a stability gate.

        Cheap enough to run before committing to a multi-minute capture, which
        is the point: the weakest single measurement decides whether that
        capture survives.
        """
        self._require_configured()
        self._emit("Probe frame")
        frame = self.acquisition.capture_frame()
        self._verify_pattern(frame, settings.pattern)
        probe = unified.probe_frame_health(frame)
        polarization = unified.analyze_polarization(frame)
        offset = unified.analyze_offset_domination(frame)
        electrodes = unified.analyze_electrode_health(frame)
        self._emit(
            f"Probe: min_current={probe.min_current_ua:.3f}uA "
            f"margin={probe.margin_ratio:.1f}x "
            f"worst_decay={polarization.worst_decay_ratio:.2f} "
            f"offset_dominated={offset.dominated_pairs}/{offset.total_pairs}"
        )
        return FrameDiagnostics(frame, probe, polarization, offset, electrodes)

    def capture_baseline(self, settings: UiSettings) -> BaselineResult:
        self._require_configured()
        self._clear_baseline()
        strict = not settings.lenient_quality
        vectors = []
        started = time.perf_counter()
        for index in range(settings.warmup_frames):
            self._raise_if_stopped()
            self.acquisition.capture_frame()
            self._emit_frame_progress(
                "Warmup frame", index, settings.warmup_frames,
                time.perf_counter() - started,
            )
        started = time.perf_counter()
        for index in range(settings.baseline_frames):
            self._raise_if_stopped(partial=list(vectors))
            frame = self.acquisition.capture_frame()
            self._raise_if_stopped(partial=list(vectors))
            self._verify_pattern(frame, settings.pattern)
            vector = unified.frame_to_vector(
                frame,
                self.protocol,
                strict=strict,
                electrode_offset=settings.electrode_offset,
                electrode_reversed=settings.electrode_reversed,
            )
            if not strict:
                dropped = len(unified.missing_value_indexes(vector))
                if dropped:
                    self._emit(
                        f"Baseline frame {index + 1}: dropped {dropped} bad measurements"
                    )
            vectors.append(vector)
            self._emit_frame_progress(
                "Baseline frame", index, settings.baseline_frames,
                time.perf_counter() - started,
            )
            self._emit_running_stability(vectors)
        baseline = unified.average_vectors(vectors)
        if not strict:
            never_measured = unified.missing_value_indexes(baseline)
            if never_measured:
                raise ValueError(
                    f"{len(never_measured)} measurements were bad in every baseline "
                    "frame; raise DAC or fix electrode contact"
                )
            vectors = [unified.fill_missing_values(vector, baseline) for vector in vectors]
        self._emit("Checking baseline stability")
        stability = unified.require_stable_baseline(
            vectors,
            allow_unstable=settings.allow_unstable_baseline,
        )
        pair_scores = unified.analyze_baseline_pair_health(vectors, self.protocol)
        result = BaselineResult(baseline, stability, pair_scores)
        self.baseline_result = result
        self.state = ControllerState.BASELINE_READY
        self._emit("Baseline ready")
        return result

    def capture_control(self, settings: UiSettings) -> unified.ControlDriftReport:
        if self.baseline_result is None:
            raise RuntimeError("baseline is required before control drift")
        strict = not settings.lenient_quality
        controls = []
        started = time.perf_counter()
        for index in range(settings.frames):
            self._raise_if_stopped(partial=list(controls))
            frame = self.acquisition.capture_frame()
            self._raise_if_stopped(partial=list(controls))
            self._verify_pattern(frame, settings.pattern)
            vector = unified.frame_to_vector(
                frame,
                self.protocol,
                strict=strict,
                electrode_offset=settings.electrode_offset,
                electrode_reversed=settings.electrode_reversed,
            )
            if not strict:
                vector = unified.fill_missing_values(vector, self.baseline_result.baseline)
            controls.append(vector)
            self._emit_frame_progress(
                "Control drift frame", index, settings.frames,
                time.perf_counter() - started,
            )
        self._emit("Analyzing control drift")
        return unified.analyze_control_drift(
            self.baseline_result.baseline,
            controls,
            self.protocol,
        )

    def capture_target(self, settings: UiSettings) -> TargetResult:
        if self.baseline_result is None:
            raise RuntimeError("baseline is required before target capture")
        strict = not settings.lenient_quality
        # Inserting the target leaves the rig idle for a minute or two, so the
        # electrode double layer restarts from cold and the first frames drift
        # while it re-equilibrates. Without discarding them the reconstruction
        # is dominated by that relaxation, which lands in the same place no
        # matter where the target actually is.
        started = time.perf_counter()
        for index in range(settings.target_warmup_frames):
            self._raise_if_stopped()
            self.acquisition.capture_frame()
            self._emit_frame_progress(
                "Target warmup frame", index, settings.target_warmup_frames,
                time.perf_counter() - started,
            )

        reconstructions = []
        healths = []
        started = time.perf_counter()
        for index in range(settings.frames):
            self._raise_if_stopped(
                partial=TargetResult(list(reconstructions), list(healths))
            )
            frame = self.acquisition.capture_frame()
            self._raise_if_stopped(
                partial=TargetResult(list(reconstructions), list(healths))
            )
            self._verify_pattern(frame, settings.pattern)
            current = unified.frame_to_vector(
                frame,
                self.protocol,
                strict=strict,
                electrode_offset=settings.electrode_offset,
                electrode_reversed=settings.electrode_reversed,
            )
            if not strict:
                current = unified.fill_missing_values(
                    current, self.baseline_result.baseline
                )
            currents = np.asarray([abs(record.current_ua) for record in frame.records])
            filtered = unified.filter_frame_vector_best_effort(
                baseline=self.baseline_result.baseline,
                current=current,
                pair_scores=self.baseline_result.pair_scores,
                current_median_ua=float(np.median(currents)),
                current_spread_ua=float(np.max(currents) - np.min(currents)),
            )
            vector_for_solver = (
                filtered.filtered_vector if settings.filter_pairs else current
            )
            dropped_for_solver = (
                filtered.dropped_indexes if settings.filter_pairs else None
            )
            total_pairs = filtered.frame_health.kept_pairs + filtered.frame_health.dropped_pairs
            self._emit(
                f"  pairs: kept={filtered.frame_health.kept_pairs}/{total_pairs} "
                f"dropped={filtered.frame_health.dropped_pairs} "
                f"({filtered.frame_health.quality_label}) "
                f"substitution={'on' if settings.filter_pairs else 'off'}"
            )
            reconstruction = base.reconstruct_difference(
                self.baseline_result.baseline,
                vector_for_solver,
                self.solver,
                dropped_indexes=dropped_for_solver,
            )
            reconstructions.append(reconstruction)
            healths.append(filtered.frame_health)
            self._target_preview(list(reconstructions))
            self._emit_frame_progress(
                "Target frame", index, settings.frames,
                time.perf_counter() - started,
            )
        self.state = ControllerState.TARGET_READY
        self._emit("Target reconstruction ready")
        return TargetResult(reconstructions, healths)

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

    def run_self_test(self, settings: UiSettings) -> selftest.SelfTestReport:
        """Check every component in ladder order and report each one separately.

        Host checks always run, so the suite is useful before a board is even
        plugged in. Hardware checks are skipped rather than failed when there is
        no connection, because "not tested" and "tested and broken" are
        different answers and merging them hides the second one.
        """
        settings.validate()
        results: list[selftest.CheckResult] = []
        self._emit("Self test: host software")
        results.append(selftest.check_protocol(settings.pattern))
        results.append(selftest.check_solver(settings.pattern))
        results.append(selftest.check_reconstruction_forward_model(settings.pattern))

        if self.state is ControllerState.DISCONNECTED:
            self._emit("Self test: not connected, skipping hardware checks")
            results.extend(self._skipped_hardware_checks("not connected"))
            return self._finish_self_test(results)

        self._emit("Self test: firmware and I2C")
        status, status_error = self._read_firmware_status()
        addresses = self._read_i2c_addresses()
        results.append(selftest.check_status_reply(status, status_error))
        results.append(selftest.check_i2c_devices(addresses))
        results.append(selftest.check_dac_binding(status, addresses))
        results.append(selftest.check_shunt(status, settings.expected_shunt_ohms))
        results.append(selftest.check_current_range(status, settings.dac))
        results.append(selftest.check_voltage_autorange(status))

        try:
            frames = self._capture_self_test_frames(settings)
        except CaptureStopped:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as a check, not a crash
            self._emit(f"Self test: frame capture failed: {exc}")
            results.extend(self._skipped_frame_checks(f"frame capture failed: {exc}"))
            return self._finish_self_test(results)

        frame = frames[0]
        probe = unified.probe_frame_health(frame)
        results.append(selftest.check_frame_shape(frame, settings.pattern))
        results.append(selftest.check_polarity_interleaving(frame))
        results.append(selftest.check_quality_flags(probe))
        results.append(selftest.check_current_margin(probe))
        results.append(selftest.check_polarization(unified.analyze_polarization(frame)))
        results.append(selftest.check_offset_domination(unified.analyze_offset_domination(frame)))
        results.append(selftest.check_voltage_resolution(frame))
        results.append(selftest.check_electrodes(unified.analyze_electrode_health(frame)))
        results.append(selftest.check_repeatability(self._self_test_vectors(frames, settings)))
        return self._finish_self_test(results)

    def _finish_self_test(self, results: list[selftest.CheckResult]) -> selftest.SelfTestReport:
        report = selftest.SelfTestReport(results)
        counts = report.counts()
        self._emit(
            f"Self test {report.status.value}: "
            f"pass={counts[selftest.CheckStatus.PASS]} "
            f"warn={counts[selftest.CheckStatus.WARN]} "
            f"fail={counts[selftest.CheckStatus.FAIL]} "
            f"skip={counts[selftest.CheckStatus.SKIP]}"
        )
        blocker = report.first_blocker()
        if blocker is not None:
            self._emit(f"Self test fix first: {blocker.component} - {blocker.name}")
        return report

    def _read_firmware_status(self) -> tuple[unified.FirmwareStatus | None, str]:
        try:
            reply = self.acquisition.send_command("?")
        except Exception as exc:  # noqa: BLE001 - becomes a FAIL check, not a crash
            return None, f"'?' command failed: {exc}"
        try:
            return unified.parse_status(reply), ""
        except ValueError as exc:
            return None, str(exc)

    def _read_i2c_addresses(self) -> list[int]:
        try:
            return unified.parse_i2c_scan(self.acquisition.send_command("i"))
        except Exception:  # noqa: BLE001 - an empty scan is itself the finding
            return []

    def _capture_self_test_frames(self, settings: UiSettings) -> list[unified.UnifiedFrame]:
        """Capture the frames the acquisition checks read, configuring if needed.

        Configuring here rather than demanding it first is what lets the self
        test be the first button pressed after Connect, which is the point of
        having it.
        """
        if self.state is ControllerState.CONNECTED or self.protocol is None:
            self.configure(settings)
        frames: list[unified.UnifiedFrame] = []
        for index in range(settings.self_test_frames):
            self._raise_if_stopped()
            frames.append(self.acquisition.capture_frame())
            self._emit(f"Self test frame {index + 1}/{settings.self_test_frames}")
        return frames

    def _self_test_vectors(
        self,
        frames: list[unified.UnifiedFrame],
        settings: UiSettings,
    ) -> list[np.ndarray]:
        """Vectors for the repeatability check.

        Lenient on purpose: one bad record should not turn a question about
        repeatability into an exception that hides every other answer.
        """
        vectors: list[np.ndarray] = []
        for frame in frames:
            if frame.pattern != settings.pattern:
                continue
            try:
                vectors.append(unified.frame_to_vector(
                    frame,
                    self.protocol,
                    strict=False,
                    electrode_offset=settings.electrode_offset,
                    electrode_reversed=settings.electrode_reversed,
                ))
            except ValueError:
                continue
        return vectors

    @staticmethod
    def _skipped_hardware_checks(reason: str) -> list[selftest.CheckResult]:
        names = (
            ("Link / firmware", "STATUS reply"),
            ("Hardware / I2C", "ADS1115 and MCP4725 present"),
            ("Hardware / DAC", "DAC bound to scanned address"),
            ("Hardware / shunt", "shunt matches fitted resistor"),
            ("Hardware / current range", "DAC within range ceiling"),
            ("Hardware / ADC", "electrode-voltage PGA autoranging"),
        )
        skipped = [
            selftest.CheckResult(component, name, selftest.CheckStatus.SKIP, reason)
            for component, name in names
        ]
        return skipped + DebugController._skipped_frame_checks(reason)

    @staticmethod
    def _skipped_frame_checks(reason: str) -> list[selftest.CheckResult]:
        names = (
            ("Acquisition / frame", "frame matches protocol"),
            ("Acquisition / frame", "forward/reverse interleaved"),
            ("Acquisition / quality", "measurement quality flags"),
            ("Acquisition / current", "weakest-measurement current margin"),
            ("Acquisition / polarisation", "current stable across an injection pair"),
            ("Acquisition / offset", "forward/reverse voltages invert"),
            ("Acquisition / resolution", "voltage readings are resolved, not quantised"),
            ("Hardware / electrodes", "all 12 electrodes live"),
            ("Acquisition / repeatability", "consecutive frames agree"),
        )
        return [
            selftest.CheckResult(component, name, selftest.CheckStatus.SKIP, reason)
            for component, name in names
        ]

    def send_command(self, command: str) -> list[str]:
        """Pass a raw firmware command through and return the reply lines."""
        if not command.strip():
            raise ValueError("command is required")
        self._emit(f"Serial command: {command.strip()}")
        return self.acquisition.send_command(command)

    def stop(self) -> None:
        self._stop_requested = True
        self._emit("STOP requested")
        self.acquisition.stop()
        self.state = ControllerState.STOPPED

    def emergency_stop(self) -> list[str]:
        """Force the hardware idle and drop the connection, best effort.

        Every step is attempted even if an earlier one fails, because the point
        is to stop current flowing; failures are returned rather than raised so
        one broken step cannot skip the rest.
        """
        errors: list[str] = []
        self._stop_requested = True
        self._emit("EMERGENCY STOP requested")
        try:
            self.acquisition.stop()
        except Exception as exc:
            errors.append(f"stop: {exc}")
        try:
            self.acquisition.close()
        except Exception as exc:
            errors.append(f"close: {exc}")
        self._clear_configuration()
        self.state = ControllerState.DISCONNECTED
        if errors:
            self._emit("EMERGENCY STOP finished with errors: " + "; ".join(errors))
        else:
            self._emit("EMERGENCY STOP done: current idle, port closed")
        return errors

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

    def _raise_if_stopped(self, partial: object = None) -> None:
        if self._stop_requested:
            raise CaptureStopped(partial=partial)

    def _emit_running_stability(self, vectors: list[np.ndarray]) -> None:
        """Report stability so far, so a diverging run can be stopped early.

        Without this the first stability number arrives only after every
        baseline frame is captured, and then it raises.
        """
        if len(vectors) < 2:
            return
        usable = [vector for vector in vectors if not np.isnan(vector).any()]
        if len(usable) < 2:
            return
        stability = unified.assess_baseline_stability(usable)
        verdict = "stable" if stability.stable else "UNSTABLE"
        self._emit(
            f"  running stability: {verdict} "
            f"relative={stability.max_relative_rms_percent:.2f}% "
            f"(limit {unified.MAX_BASELINE_RELATIVE_RMS_PERCENT:.2f}%) "
            f"corr={stability.min_correlation:.5f} "
            f"(limit {unified.MIN_BASELINE_CORRELATION:.5f})"
        )

    def _emit_frame_progress(
        self,
        label: str,
        index: int,
        total: int,
        elapsed_seconds: float,
    ) -> None:
        """Progress line with a remaining-time estimate from measured frames."""
        completed = index + 1
        message = f"{label} {completed}/{total}"
        if completed and elapsed_seconds > 0.0:
            per_frame = elapsed_seconds / completed
            remaining = per_frame * (total - completed)
            message += f" ({per_frame:.1f}s/frame, ~{remaining:.0f}s left)"
        self._emit(message)

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
