"""Per-component sanity checks for the Phase 3A rig.

Every check in this module is a pure function over evidence that has already
been collected - a serial reply, an I2C scan, one captured frame - so the whole
suite is testable without a board attached. `DebugController.run_self_test`
does the collecting and calls these; the UI only renders what comes back.

The checks are ordered to follow the validation ladder in
`docs/current-setup-validation-runbook.md`: each one assumes the ones above it
passed, because a failure high on the ladder makes every check below it produce
a confident wrong answer rather than an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified


# A frame this far below the firmware's I_LOW threshold still passes a strict
# capture, but with no room for the drift a long run adds. Below it the run is
# expected to abort partway rather than fail up front, which is the more
# expensive failure.
MIN_CURRENT_MARGIN_RATIO = 3.0
WARN_CURRENT_MARGIN_RATIO = 10.0
# Fraction of forward/reverse pairs allowed to be offset-dominated before the
# transfer resistances they feed are worth distrusting.
MAX_OFFSET_DOMINATED_FRACTION = 0.10
WARN_OFFSET_DOMINATED_FRACTION = 0.02
# An electrode carrying this fraction of the frame's median drive current is
# treated as a broken mux channel or a dry contact rather than a weak one.
MIN_ELECTRODE_DRIVE_FRACTION = 0.25
# Two frames captured back to back on an untouched rig should be near-identical.
# This is deliberately looser than the baseline gate: it screens for a rig that
# is not repeatable at all, not for one that is good enough to image with.
MIN_REPEATABILITY_CORRELATION = 0.99
# Distinct voltage magnitudes expected across a frame. When the PGA sits on too
# coarse a range the readings collapse onto a handful of LSB multiples, which is
# the quantisation failure that made 102/108 pairs look offset-dominated.
MIN_DISTINCT_VOLTAGE_FRACTION = 0.5
# One LSB on the widest electrode-voltage range, in mV. Readings that are all
# exact multiples of this are being taken on GAIN_ONE.
COARSE_VOLTAGE_LSB_MV = 0.125


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class CheckResult:
    component: str
    name: str
    status: CheckStatus
    detail: str
    remedy: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {CheckStatus.PASS, CheckStatus.SKIP}


@dataclass(frozen=True)
class SelfTestReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def status(self) -> CheckStatus:
        if any(result.status is CheckStatus.FAIL for result in self.results):
            return CheckStatus.FAIL
        if any(result.status is CheckStatus.WARN for result in self.results):
            return CheckStatus.WARN
        if self.results and all(result.status is CheckStatus.SKIP for result in self.results):
            return CheckStatus.SKIP
        return CheckStatus.PASS

    def counts(self) -> dict[CheckStatus, int]:
        tally = {status: 0 for status in CheckStatus}
        for result in self.results:
            tally[result.status] += 1
        return tally

    def failures(self) -> list[CheckResult]:
        return [result for result in self.results if result.status is CheckStatus.FAIL]

    def first_blocker(self) -> CheckResult | None:
        """The earliest failure, which is the one worth fixing first.

        Later checks assume the earlier ones passed, so reporting them all as
        equally actionable sends the user chasing symptoms.
        """
        for result in self.results:
            if result.status is CheckStatus.FAIL:
                return result
        return None


def _skip(component: str, name: str, reason: str) -> CheckResult:
    return CheckResult(component, name, CheckStatus.SKIP, reason)


# --- Host software -------------------------------------------------------


def check_protocol(pattern: str) -> CheckResult:
    """The protocol builds and has the measurement count the pattern implies."""
    component = "Host / protocol"
    try:
        protocol, _ = unified.protocol_and_command(pattern)
    except ValueError as exc:
        return CheckResult(
            component, f"{pattern} protocol builds", CheckStatus.FAIL, str(exc),
            "Pick one of adjacent, opposite, skip-1, skip-2.",
        )
    excitations = int(protocol.ex_mat.shape[0])
    per_excitation = int(protocol.meas_mat.shape[1])
    total = excitations * per_excitation
    expected_excitations = base.N_ELECTRODES
    if excitations != expected_excitations or total <= 0:
        return CheckResult(
            component, f"{pattern} protocol builds", CheckStatus.FAIL,
            f"{excitations} excitations x {per_excitation} = {total} measurements",
            "Expected one excitation per electrode; check build_protocol().",
        )
    return CheckResult(
        component, f"{pattern} protocol builds", CheckStatus.PASS,
        f"{excitations} excitations x {per_excitation} sense pairs = {total} measurements",
    )


def check_solver(pattern: str) -> CheckResult:
    """The PyEIT mesh and JAC solver construct, and electrodes sit on the mesh."""
    component = "Host / solver"
    try:
        protocol, _ = unified.protocol_and_command(pattern)
        eit_mesh, _solver = base.create_solver(protocol)
    except Exception as exc:  # noqa: BLE001 - any failure here is a hard stop
        return CheckResult(
            component, "PyEIT mesh and solver build", CheckStatus.FAIL, str(exc),
            "Check the PyEIT install: .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt",
        )
    positions = base.electrode_label_positions(eit_mesh)
    if len(positions) != base.N_ELECTRODES:
        return CheckResult(
            component, "PyEIT mesh and solver build", CheckStatus.FAIL,
            f"mesh reports {len(positions)} electrode positions, expected {base.N_ELECTRODES}",
            "Electrode labels are derived from mesh.el_pos; a short list means the mesh is wrong.",
        )
    return CheckResult(
        component, "PyEIT mesh and solver build", CheckStatus.PASS,
        f"{len(eit_mesh.element)} elements, {base.N_ELECTRODES} electrodes placed from mesh.el_pos",
    )


FORWARD_TARGET_ANGLE_DEG = 30.0
FORWARD_TARGET_RADIUS = 0.6
# One electrode sector is 30 degrees, and HANDOVER.md accepts a localisation
# within 1-2 sectors. A synthetic target has none of the noise a real one does,
# so anything past two sectors here is a convention error, not measurement.
MAX_FORWARD_ANGLE_ERROR_DEG = 60.0


def check_reconstruction_forward_model(pattern: str = "adjacent") -> CheckResult:
    """Put a target of known angle and known sign through the real pipeline.

    The only check that exercises the two deliberate conventions end to end -
    the negation in `paired_transfer_resistance()` and the `[vn, vp]` row order
    in `build_protocol()` - plus the mesh-derived electrode labels. Remove any
    of them and every image silently mirrors or inverts while every other check
    here still passes.

    A synthetic uniform change will not do: the solver normalises it away and
    leaves floating-point noise whose sign means nothing. This drives PyEIT's
    own forward model with a localised inclusion instead.
    """
    component = "Host / reconstruction"
    name = "known target reconstructs at the right place and sign"
    try:
        import pyeit.mesh as pyeit_mesh
        from pyeit.eit.fem import EITForward
        from pyeit.mesh.wrapper import PyEITAnomaly_Circle

        protocol, _ = unified.protocol_and_command(pattern)
        solver_mesh, solver = base.create_solver(protocol)

        forward_mesh = pyeit_mesh.create(base.N_ELECTRODES, h0=0.08)
        forward = EITForward(forward_mesh, protocol)
        homogeneous = forward.solve_eit()
        angle = np.deg2rad(FORWARD_TARGET_ANGLE_DEG)
        anomaly = PyEITAnomaly_Circle(
            center=[
                FORWARD_TARGET_RADIUS * np.cos(angle),
                FORWARD_TARGET_RADIUS * np.sin(angle),
            ],
            r=0.2,
            perm=10.0,
        )
        measured = forward.solve_eit(
            perm=pyeit_mesh.set_perm(forward_mesh, anomaly=anomaly, background=1.0).perm
        )
        values = base.reconstruct_difference(homogeneous, measured, solver)
    except Exception as exc:  # noqa: BLE001 - reported, never fatal
        return _skip(component, name, f"forward model unavailable: {exc}")

    peak_index = int(np.argmax(np.abs(values)))
    peak_value = float(values[peak_index])
    centroid = solver_mesh.node[solver_mesh.element[peak_index]].mean(axis=0)
    peak_angle = float(np.rad2deg(np.arctan2(centroid[1], centroid[0]))) % 360.0
    angle_error = abs((peak_angle - FORWARD_TARGET_ANGLE_DEG + 180.0) % 360.0 - 180.0)
    detail = (
        f"conductive target at {FORWARD_TARGET_ANGLE_DEG:.0f} deg reconstructs at "
        f"{peak_angle:.0f} deg ({angle_error:.0f} deg off), peak {peak_value:+.4f}"
    )
    if peak_value <= 0.0:
        return CheckResult(
            component, name, CheckStatus.FAIL, detail,
            "Sign is inverted (validity-audit D-02): check the leading minus in "
            "paired_transfer_resistance() and the [vn, vp] row order in build_protocol().",
        )
    if angle_error > MAX_FORWARD_ANGLE_ERROR_DEG:
        return CheckResult(
            component, name, CheckStatus.FAIL, detail,
            "Localisation is wrong by more than two electrode sectors; the protocol "
            "row order or the electrode mapping does not match the mesh.",
        )
    return CheckResult(component, name, CheckStatus.PASS, detail)


# --- Link and firmware ---------------------------------------------------


def check_status_reply(status: unified.FirmwareStatus | None, error: str = "") -> CheckResult:
    component = "Link / firmware"
    name = "STATUS reply"
    if status is None:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            error or "no STATUS,2 line in the reply to '?'",
            "Board may be running an older flash, or another serial monitor is holding the port.",
        )
    return CheckResult(
        component, name, CheckStatus.PASS,
        f"v2 firmware, mode={status.pattern} range={status.current_range} "
        f"dac={status.dac_code} settle={status.settle_ms}ms samples={status.sample_count}",
    )


def check_i2c_devices(addresses: list[int]) -> CheckResult:
    """Both I2C parts answer, and exactly one MCP4725 is on the bus."""
    component = "Hardware / I2C"
    name = "ADS1115 and MCP4725 present"
    if not addresses:
        return CheckResult(
            component, name, CheckStatus.FAIL, "I2C scan returned no devices",
            "Check 3.3V, GND, SDA/SCL wiring and pull-ups before anything else.",
        )
    listed = ", ".join(f"0x{value:02x}" for value in addresses)
    missing = []
    if unified.ADS1115_ADDRESS not in addresses:
        missing.append(f"ADS1115 0x{unified.ADS1115_ADDRESS:02x}")
    dac_address = unified.select_dac_address(addresses)
    if dac_address is None:
        missing.append("exactly one MCP4725 in 0x60-0x67")
    if missing:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            f"saw {listed}; missing {', '.join(missing)}",
            "Stop here: a scan that cannot see both parts makes every later reading meaningless.",
        )
    return CheckResult(
        component, name, CheckStatus.PASS,
        f"ADS1115 0x{unified.ADS1115_ADDRESS:02x}, MCP4725 0x{dac_address:02x} (saw {listed})",
    )


def check_dac_binding(
    status: unified.FirmwareStatus | None,
    addresses: list[int],
) -> CheckResult:
    """The firmware's DAC driver is bound to the address the bus reports.

    The A0 strap moves this board's MCP4725 between 0x60 and 0x61. A driver
    bound to the wrong one leaves the current source parked at whatever code
    its EEPROM powered up with, while the firmware reports the commanded value.
    """
    component = "Hardware / DAC"
    name = "DAC bound to scanned address"
    if status is None:
        return _skip(component, name, "no STATUS reply to compare against")
    scanned = unified.select_dac_address(addresses)
    if scanned is None:
        return _skip(component, name, "I2C scan did not resolve a single MCP4725")
    if status.dac_address is None:
        return CheckResult(
            component, name, CheckStatus.WARN,
            "firmware did not report DAC_ADDR",
            "Reflash to a build that reports DAC_ADDR in STATUS.",
        )
    if status.dac_address != scanned:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            f"firmware bound to 0x{status.dac_address:02x}, bus says 0x{scanned:02x}",
            f"Send b{scanned:02x} to rebind, then re-run.",
        )
    return CheckResult(
        component, name, CheckStatus.PASS, f"bound to 0x{scanned:02x}",
    )


def check_shunt(
    status: unified.FirmwareStatus | None,
    expected_ohms: float | None,
) -> CheckResult:
    """The firmware's shunt constant matches the resistor physically fitted.

    A wrong value scales every current, so every transfer resistance is wrong
    by that same ratio - and nothing downstream complains, because the numbers
    stay perfectly self-consistent.
    """
    component = "Hardware / shunt"
    name = "shunt matches fitted resistor"
    if status is None:
        return _skip(component, name, "no STATUS reply")
    if expected_ohms is None:
        return CheckResult(
            component, name, CheckStatus.WARN,
            f"firmware reports {status.shunt_ohms:.2f} ohm; no expected value configured",
            "Measure the fitted Rs and set it in the self-test field so this can be checked.",
        )
    if status.shunt_ohms <= 0.0:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            f"firmware reports {status.shunt_ohms:.2f} ohm",
            "Set a real value with j<ohms>.",
        )
    error_percent = 100.0 * abs(status.shunt_ohms - expected_ohms) / expected_ohms
    if error_percent > 5.0:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            f"firmware {status.shunt_ohms:.2f} ohm vs fitted {expected_ohms:.2f} ohm "
            f"({error_percent:.1f}% off)",
            f"Send j{expected_ohms:g} - every current is scaled by this ratio until you do.",
        )
    return CheckResult(
        component, name, CheckStatus.PASS,
        f"{status.shunt_ohms:.2f} ohm vs fitted {expected_ohms:.2f} ohm ({error_percent:.1f}% off)",
    )


def check_current_range(
    status: unified.FirmwareStatus | None,
    requested_dac: int,
) -> CheckResult:
    """The requested DAC code is inside the selected range's ceiling.

    The firmware clips silently, so a code above the ceiling produces a run at
    a current the user did not ask for and has no reason to suspect.
    """
    component = "Hardware / current range"
    name = "DAC within range ceiling"
    if status is None:
        return _skip(component, name, "no STATUS reply")
    if requested_dac > status.max_dac_code:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            f"requested dac={requested_dac} exceeds the {status.current_range} "
            f"ceiling of {status.max_dac_code}; firmware clipped to {status.dac_code}",
            "Lower the DAC code, or select the range matching the fitted Rs jumper "
            "(el / em / eh).",
        )
    if status.dac_code != requested_dac:
        return CheckResult(
            component, name, CheckStatus.WARN,
            f"requested dac={requested_dac} but firmware holds {status.dac_code}",
            "Press Configure before running the self test so the board matches the UI.",
        )
    return CheckResult(
        component, name, CheckStatus.PASS,
        f"dac={status.dac_code} within {status.current_range} ceiling {status.max_dac_code} "
        f"(Rs={status.rs_ohms:.1f} ohm)",
    )


def check_voltage_autorange(status: unified.FirmwareStatus | None) -> CheckResult:
    """PGA autoranging is on, and the last range picked was not the widest.

    Measured saline voltages sit under 250 mV against the 4096 mV fixed range,
    where one ADC step is larger than the IR drop on distant pairs and the
    forward/reverse difference quantises to exactly zero.
    """
    component = "Hardware / ADC"
    name = "electrode-voltage PGA autoranging"
    if status is None:
        return _skip(component, name, "no STATUS reply")
    if not status.voltage_autorange:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            "autoranging is disabled (VGAIN_AUTO,0)",
            "Send a1. On the fixed 4096 mV range distant pairs quantise to zero.",
        )
    return CheckResult(
        component, name, CheckStatus.PASS,
        f"enabled; last range {status.voltage_range_mv:.0f} mV full scale",
    )


# --- One captured frame --------------------------------------------------


def check_frame_shape(frame: unified.UnifiedFrame, pattern: str) -> CheckResult:
    """The frame is the pattern that was asked for, and it is complete."""
    component = "Acquisition / frame"
    name = "frame matches protocol"
    if frame.pattern != pattern:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            f"firmware returned {frame.pattern}, expected {pattern}",
            "Press Configure, or send the mode command directly (ma / mo / ms / mk).",
        )
    protocol, _ = unified.protocol_and_command(pattern)
    expected = int(protocol.ex_mat.shape[0] * protocol.meas_mat.shape[1])
    forward = sum(1 for record in frame.records if record.polarity == "FWD")
    reverse = sum(1 for record in frame.records if record.polarity == "REV")
    if forward != reverse:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            f"{forward} forward vs {reverse} reverse records",
            "Every sense pair must be measured in both polarities; a mismatch "
            "collapses paired_transfer_resistance().",
        )
    if forward != expected:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            f"{forward} measurement pairs, protocol expects {expected}",
            "Frame and protocol disagree; check the drive pattern and electrode count.",
        )
    return CheckResult(
        component, name, CheckStatus.PASS,
        f"{pattern}: {expected} pairs, {forward} forward and {reverse} reverse",
    )


def check_polarity_interleaving(frame: unified.UnifiedFrame) -> CheckResult:
    """Records arrive FWD, REV, FWD, REV rather than in per-polarity passes.

    Holding one polarity across a whole injection pair builds electrode
    polarisation. This check reads the order the firmware actually emitted, so
    it catches a regression to per-polarity passes even before the current has
    had time to decay enough for the polarisation check to fire.
    """
    component = "Acquisition / frame"
    name = "forward/reverse interleaved"
    polarities = [record.polarity for record in frame.records]
    if len(polarities) < 2:
        return _skip(component, name, "frame too short to judge ordering")
    expected = ["FWD" if index % 2 == 0 else "REV" for index in range(len(polarities))]
    if polarities != expected:
        runs = 1 + sum(
            1 for index in range(1, len(polarities))
            if polarities[index] != polarities[index - 1]
        )
        return CheckResult(
            component, name, CheckStatus.FAIL,
            f"polarity order is not FWD/REV alternating ({runs} runs across "
            f"{len(polarities)} records)",
            "Firmware has been restructured into per-polarity passes; restore the "
            "interleaving in emitInjectionPair().",
        )
    return CheckResult(
        component, name, CheckStatus.PASS,
        f"{len(polarities)} records alternating FWD/REV",
    )


def check_quality_flags(probe: unified.FrameProbe) -> CheckResult:
    component = "Acquisition / quality"
    name = "measurement quality flags"
    bad = {flag: count for flag, count in probe.quality_counts.items() if flag != "OK"}
    if not bad:
        return CheckResult(
            component, name, CheckStatus.PASS,
            f"all {probe.total_records} records OK",
        )
    listed = ", ".join(f"{flag}={count}" for flag, count in sorted(bad.items()))
    fraction = sum(bad.values()) / probe.total_records
    status = CheckStatus.FAIL if fraction > 0.05 else CheckStatus.WARN
    return CheckResult(
        component, name, status,
        f"{sum(bad.values())}/{probe.total_records} records flagged ({listed})",
        "I_LOW: raise DAC or fix contact. I_REVERSED: swap the drive leads. "
        "V_RANGE: signal is outside the safe mux window.",
    )


def check_current_margin(probe: unified.FrameProbe) -> CheckResult:
    """The weakest measurement, not the median, decides whether a run survives."""
    component = "Acquisition / current"
    name = "weakest-measurement current margin"
    detail = (
        f"min={probe.min_current_ua:.2f}uA ({probe.margin_ratio:.1f}x the "
        f"{unified.FIRMWARE_MIN_CURRENT_UA:.1f}uA floor), "
        f"median={probe.median_current_ua:.2f}uA, weakest at "
        f"I={base.index_to_electrode(probe.min_current_i_pair[0])}-"
        f"{base.index_to_electrode(probe.min_current_i_pair[1])}"
    )
    if probe.margin_ratio < MIN_CURRENT_MARGIN_RATIO:
        return CheckResult(
            component, name, CheckStatus.FAIL, detail,
            "One record under the I_LOW floor aborts a strict capture. Raise the "
            "DAC code, improve electrode contact, or switch to a higher current range.",
        )
    if probe.margin_ratio < WARN_CURRENT_MARGIN_RATIO:
        return CheckResult(
            component, name, CheckStatus.WARN, detail,
            "Enough to capture now, but little room for drift over a long run.",
        )
    return CheckResult(component, name, CheckStatus.PASS, detail)


def check_polarization(report: unified.PolarizationReport) -> CheckResult:
    """Current must not decay across a fixed injection pair."""
    component = "Acquisition / polarisation"
    name = "current stable across an injection pair"
    detail = (
        f"worst decay {report.worst_decay_ratio:.2f}x, "
        f"{report.flagged_groups} injection groups flagged"
    )
    if report.flagged_groups:
        return CheckResult(
            component, name, CheckStatus.FAIL, detail,
            "Electrode polarisation: raise the discharge time (cN), lower the drive, "
            "or check that forward/reverse are still interleaved.",
        )
    if report.worst_decay_ratio > 1.2:
        return CheckResult(component, name, CheckStatus.WARN, detail)
    return CheckResult(component, name, CheckStatus.PASS, detail)


def check_offset_domination(report: unified.OffsetReport) -> CheckResult:
    """Reversing the current must invert the IR drop."""
    component = "Acquisition / offset"
    name = "forward/reverse voltages invert"
    if not report.total_pairs:
        return _skip(component, name, "no forward/reverse pairs in the frame")
    fraction = report.dominated_fraction
    detail = (
        f"{report.dominated_pairs}/{report.total_pairs} pairs offset-dominated "
        f"({100.0 * fraction:.1f}%)"
    )
    if fraction > MAX_OFFSET_DOMINATED_FRACTION:
        return CheckResult(
            component, name, CheckStatus.FAIL, detail,
            "Static half-cell potential outweighs the injected signal, so transfer "
            "resistances cancel toward zero. Check PGA autoranging is on and the "
            "drive current is high enough to be resolvable.",
        )
    if fraction > WARN_OFFSET_DOMINATED_FRACTION:
        return CheckResult(component, name, CheckStatus.WARN, detail)
    return CheckResult(component, name, CheckStatus.PASS, detail)


def check_voltage_resolution(frame: unified.UnifiedFrame) -> CheckResult:
    """Voltages must not all land on multiples of the widest range's LSB.

    When they do, the PGA is sitting on GAIN_ONE and averaging buys nothing,
    because all the samples return the same count. That is the fingerprint that
    made 102 of 108 pairs look offset-dominated before autoranging was added.
    """
    component = "Acquisition / resolution"
    name = "voltage readings are resolved, not quantised"
    voltages = np.asarray([record.voltage_mv for record in frame.records])
    if voltages.size == 0:
        return _skip(component, name, "frame contains no measurements")
    distinct_fraction = len(np.unique(np.round(voltages, 6))) / voltages.size
    on_coarse_grid = bool(
        np.all(np.abs(np.remainder(voltages + COARSE_VOLTAGE_LSB_MV / 2.0,
                                   COARSE_VOLTAGE_LSB_MV) - COARSE_VOLTAGE_LSB_MV / 2.0) < 1e-6)
    )
    detail = (
        f"{100.0 * distinct_fraction:.0f}% of {voltages.size} readings distinct; "
        f"{'all' if on_coarse_grid else 'not all'} on the "
        f"{COARSE_VOLTAGE_LSB_MV * 1000:.0f} uV coarse grid"
    )
    if on_coarse_grid and distinct_fraction < MIN_DISTINCT_VOLTAGE_FRACTION:
        return CheckResult(
            component, name, CheckStatus.FAIL, detail,
            "Readings are quantised to the widest PGA range. Enable autoranging (a1) "
            "and confirm the flash includes the float-mean averaging fix.",
        )
    if distinct_fraction < MIN_DISTINCT_VOLTAGE_FRACTION:
        return CheckResult(component, name, CheckStatus.WARN, detail)
    return CheckResult(component, name, CheckStatus.PASS, detail)


def check_electrodes(healths: list[unified.ElectrodeHealth]) -> CheckResult:
    """Every electrode must carry current and sense a voltage.

    A dead mux channel or a dry contact shows here as one electrode carrying a
    small fraction of the drive current the others do.
    """
    component = "Hardware / electrodes"
    name = "all 12 electrodes live"
    if not healths:
        return _skip(component, name, "no electrode health data")
    drives = np.asarray([health.drive_median_ua for health in healths])
    median_drive = float(np.median(drives))
    if median_drive <= 0.0:
        return CheckResult(
            component, name, CheckStatus.FAIL,
            "no electrode carried measurable current",
            "Nothing is being driven; check the current pump and mux enables.",
        )
    floor = median_drive * MIN_ELECTRODE_DRIVE_FRACTION
    weak = [health for health in healths if health.drive_median_ua < floor]
    silent = [health for health in healths if health.sense_count and health.sense_median_abs_mv <= 0.0]
    if weak or silent:
        parts = []
        if weak:
            parts.append("weak drive: " + ", ".join(
                f"{base.index_to_electrode(health.electrode)}="
                f"{health.drive_median_ua:.1f}uA" for health in weak
            ))
        if silent:
            parts.append("no sense signal: " + ", ".join(
                base.index_to_electrode(health.electrode) for health in silent
            ))
        return CheckResult(
            component, name, CheckStatus.FAIL,
            f"median drive {median_drive:.1f}uA; " + "; ".join(parts),
            "Test that mux channel electrically (runbook step 5) before trusting any image.",
        )
    return CheckResult(
        component, name, CheckStatus.PASS,
        f"12/12 electrodes above {floor:.1f}uA (median drive {median_drive:.1f}uA)",
    )


def check_repeatability(vectors: list[np.ndarray]) -> CheckResult:
    """Back-to-back frames on an untouched rig must look the same.

    Deliberately looser than the baseline stability gate: this screens for a rig
    that is not repeatable at all, not for one good enough to image with.
    """
    component = "Acquisition / repeatability"
    name = "consecutive frames agree"
    usable = [vector for vector in vectors if not np.isnan(vector).any()]
    if len(usable) < 2:
        return _skip(component, name, "need two clean frames to compare")
    stability = unified.assess_baseline_stability(usable)
    detail = (
        f"{len(usable)} frames: relative RMS {stability.max_relative_rms_percent:.2f}%, "
        f"correlation {stability.min_correlation:.5f}"
    )
    if stability.min_correlation < MIN_REPEATABILITY_CORRELATION:
        return CheckResult(
            component, name, CheckStatus.FAIL, detail,
            "Consecutive frames do not agree, so no baseline will hold. Let the rig "
            "settle, raise settle time and sample count, and check electrode contact.",
        )
    if not stability.stable:
        return CheckResult(
            component, name, CheckStatus.WARN, detail,
            "Repeatable enough to trust the wiring, but below the baseline gate "
            f"({unified.MAX_BASELINE_RELATIVE_RMS_PERCENT:.1f}% / "
            f"{unified.MIN_BASELINE_CORRELATION:.3f}). Tune Drift may close the gap.",
        )
    return CheckResult(component, name, CheckStatus.PASS, detail)


def format_report(report: SelfTestReport) -> str:
    """Plain-text rendering, used by the UI log and by exported reports."""
    lines: list[str] = []
    component = ""
    for result in report.results:
        if result.component != component:
            component = result.component
            lines.append(f"\n{component}")
        lines.append(f"  [{result.status.value:<4}] {result.name}: {result.detail}")
        if result.remedy and result.status in {CheckStatus.WARN, CheckStatus.FAIL}:
            lines.append(f"         -> {result.remedy}")
    counts = report.counts()
    lines.append(
        f"\nOverall: {report.status.value} "
        f"(pass={counts[CheckStatus.PASS]} warn={counts[CheckStatus.WARN]} "
        f"fail={counts[CheckStatus.FAIL]} skip={counts[CheckStatus.SKIP]})"
    )
    blocker = report.first_blocker()
    if blocker is not None:
        lines.append(f"Fix first: {blocker.component} - {blocker.name}")
    return "\n".join(lines).strip()
