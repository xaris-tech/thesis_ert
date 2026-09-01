from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
from phase3a_reconstruct import N_ELECTRODES
from tree_ert import selftest
from tree_ert.acquisition import DemoAcquisition, SerialAcquisition
from tree_ert.controller import (
    CaptureStopped,
    DebugController,
    DriftTuneAttempt,
    DriftTuneResult,
    FrameDiagnostics,
    TargetResult,
)
from tree_ert.settings import (
    UiSettings,
    load_settings,
    parse_float_field,
    parse_int_field,
    save_settings,
    settings_path,
)


def available_ports() -> tuple[str, ...]:
    """Serial ports currently present, newest listing each call."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return ()
    return tuple(sorted(port.device for port in list_ports.comports()))


def _electrode_pair(pair: tuple[int, int]) -> str:
    return f"{base.index_to_electrode(pair[0])}-{base.index_to_electrode(pair[1])}"


def format_frame_probe(probe: unified.FrameProbe) -> str:
    qualities = ", ".join(
        f"{name}={count}" for name, count in sorted(probe.quality_counts.items())
    )
    verdict = "PASS" if probe.passes else "FAIL"
    return (
        f"Probe {verdict}: min_current={probe.min_current_ua:.3f}uA "
        f"({probe.margin_ratio:.1f}x the {unified.FIRMWARE_MIN_CURRENT_UA:.1f}uA floor) "
        f"at {probe.min_current_polarity} "
        f"I={_electrode_pair(probe.min_current_i_pair)} "
        f"V={_electrode_pair(probe.min_current_v_pair)}; "
        f"median_current={probe.median_current_ua:.3f}uA; "
        f"records={probe.total_records}; qualities: {qualities}"
    )


def format_polarization_summary(report: unified.PolarizationReport) -> str:
    if not report.metrics:
        return "Polarisation: not enough measurements per injection pair to assess"
    worst = report.metrics[0]
    verdict = "FLAGGED" if report.flagged else "ok"
    return (
        f"Polarisation {verdict}: worst_decay={report.worst_decay_ratio:.2f}x "
        f"(limit {unified.MAX_POLARIZATION_DECAY_RATIO:.2f}x) "
        f"at I={_electrode_pair(worst.i_pair)} {worst.polarity} "
        f"{worst.first_current_ua:.2f}uA -> {worst.last_current_ua:.2f}uA "
        f"over {worst.sample_count} measurements; "
        f"flagged_groups={report.flagged_groups}/{len(report.metrics)}"
    )


def format_offset_summary(report: unified.OffsetReport) -> str:
    if not report.pairs:
        return "Offset: no forward/reverse pairs to compare"
    worst = report.pairs[0]
    verdict = "FLAGGED" if report.flagged else "ok"
    return (
        f"Offset {verdict}: {report.dominated_pairs}/{report.total_pairs} pairs "
        f"({100.0 * report.dominated_fraction:.1f}%) dominated by electrode offset "
        f"(limit {unified.MAX_OFFSET_COMMON_RATIO:.2f}); "
        f"worst I={_electrode_pair(worst.i_pair)} V={_electrode_pair(worst.v_pair)} "
        f"fwd={worst.forward_mv:.3f}mV rev={worst.reverse_mv:.3f}mV "
        f"differential={worst.differential_mv:.3f}mV common={worst.common_mv:.3f}mV"
    )


def format_electrode_health_summary(
    electrodes: list[unified.ElectrodeHealth],
    limit: int = 3,
) -> str:
    if not electrodes:
        return "Electrodes: no data"
    weakest = sorted(electrodes, key=lambda item: item.drive_median_ua)[:limit]
    parts = [
        f"{base.index_to_electrode(item.electrode)} "
        f"drive={item.drive_median_ua:.2f}uA "
        f"sense={item.sense_median_abs_mv:.2f}mV "
        f"bad={item.bad_quality_count}"
        for item in weakest
    ]
    return "Weakest electrodes by drive current: " + "; ".join(parts)


def describe_partial_capture(partial: object) -> str:
    """One line naming what a stopped capture managed to keep."""
    if partial is None:
        return "no partial data kept"
    if isinstance(partial, TargetResult):
        count = len(partial.reconstructions)
        return f"kept {count} target reconstruction(s)" if count else "no partial data kept"
    if isinstance(partial, list):
        return f"kept {len(partial)} frame vector(s)" if partial else "no partial data kept"
    return "partial data kept"


def format_frame_diagnostics(diagnostics: FrameDiagnostics) -> str:
    return "\n".join((
        format_frame_probe(diagnostics.probe),
        format_polarization_summary(diagnostics.polarization),
        format_offset_summary(diagnostics.offset),
        format_electrode_health_summary(diagnostics.electrodes),
    ))


def average_reconstruction_vector(reconstructions: list[np.ndarray]) -> np.ndarray:
    if not reconstructions:
        return np.asarray([], dtype=float)
    return np.mean(np.stack(reconstructions), axis=0)


def latest_reconstruction(reconstructions: list[np.ndarray]) -> np.ndarray:
    """Most recent scan.

    The main map shows this rather than a running average: averaging hides how
    much a target run moves between scans, which is exactly what has to be
    judged while the rig is still being stabilised.
    """
    if not reconstructions:
        return np.asarray([], dtype=float)
    return reconstructions[-1]


def build_reconstruction_figure() -> tuple[Figure, object, object, tuple[object, ...]]:
    figure = Figure(figsize=(10, 6.5), dpi=100)
    grid = figure.add_gridspec(2, 4, height_ratios=(3.0, 1.15))
    map_ax = figure.add_subplot(grid[0, 0:2])
    vector_ax = figure.add_subplot(grid[0, 2:4])
    scan_axes = tuple(figure.add_subplot(grid[1, index]) for index in range(4))
    map_ax.set_title("Latest scan map")
    map_ax.set_aspect("equal")
    map_ax.set_axis_off()
    vector_ax.set_title("Latest reconstruction vector")
    vector_ax.set_xlabel("Vector index")
    vector_ax.set_ylabel("Difference")
    for index, axis in enumerate(scan_axes, start=1):
        axis.set_title(f"Scan {index}")
        axis.set_axis_off()
    figure.tight_layout()
    return figure, map_ax, vector_ax, scan_axes


def preview_scan_indices(scan_count: int, preview_count: int = 4) -> tuple[int, ...]:
    if scan_count <= 0:
        return ()
    if scan_count <= preview_count:
        return tuple(range(scan_count))
    return tuple(int(round(index)) for index in np.linspace(0, scan_count - 1, preview_count))


def debug_tab_titles() -> tuple[str, ...]:
    return ("Reconstruction", "Self Test", "Health", "Serial", "Files")


SELF_TEST_STATUS_COLORS = {
    selftest.CheckStatus.PASS: "#0b6b3a",
    selftest.CheckStatus.WARN: "#8a5a00",
    selftest.CheckStatus.FAIL: "#b00020",
    selftest.CheckStatus.SKIP: "#666666",
}


def format_self_test_summary(report: selftest.SelfTestReport) -> str:
    counts = report.counts()
    summary = (
        f"Self test {report.status.value}: "
        f"pass={counts[selftest.CheckStatus.PASS]} "
        f"warn={counts[selftest.CheckStatus.WARN]} "
        f"fail={counts[selftest.CheckStatus.FAIL]} "
        f"skip={counts[selftest.CheckStatus.SKIP]}"
    )
    blocker = report.first_blocker()
    if blocker is not None:
        summary += f" | fix first: {blocker.component} - {blocker.name}"
    return summary


def format_control_drift_summary(report: unified.ControlDriftReport) -> str:
    if not report.frames:
        return "Control drift result: no frames analyzed"
    max_rms = max(frame.rms_kohm for frame in report.frames)
    max_relative = max(frame.relative_rms_percent for frame in report.frames)
    min_correlation = min(frame.correlation for frame in report.frames)
    summary = (
        "Control drift result: "
        f"frames={len(report.frames)} "
        f"max_rms={max_rms:.6f}kOhm "
        f"max_relative={max_relative:.2f}% "
        f"min_corr={min_correlation:.6f}"
    )
    if report.pairs:
        pair = report.pairs[0]
        summary += (
            " "
            f"worst_pair=I={base.index_to_electrode(pair.i_pair[0])}-"
            f"{base.index_to_electrode(pair.i_pair[1])} "
            f"V={base.index_to_electrode(pair.v_pair[0])}-"
            f"{base.index_to_electrode(pair.v_pair[1])} "
            f"pair_rms={pair.rms_kohm:.6f}kOhm"
        )
    if report.electrodes:
        electrode = report.electrodes[0]
        summary += (
            " "
            f"worst_electrode={base.index_to_electrode(electrode.electrode)} "
            f"electrode_mean_rms={electrode.mean_pair_rms_kohm:.6f}kOhm"
        )
    return summary


def format_drift_tune_summary(result: DriftTuneResult) -> str:
    if result.best is None:
        return f"Drift tuning result: no successful attempts out of {len(result.attempts)}"
    best = result.best
    return (
        "Drift tuning result: "
        f"best_settle={best.settings.settle_ms}ms "
        f"best_samples={best.settings.samples} "
        f"best_warmup={best.settings.warmup_frames} "
        f"best_baseline={best.settings.baseline_frames} "
        f"best_control_frames={best.settings.frames} "
        f"max_relative={best.max_relative_rms_percent:.2f}% "
        f"max_rms={best.max_rms_kohm:.6f}kOhm "
        f"min_corr={best.min_correlation:.6f}"
    )


def format_drift_tune_attempt(attempt: DriftTuneAttempt) -> str:
    settings = attempt.settings
    prefix = (
        f"Tune attempt settle={settings.settle_ms}ms samples={settings.samples} "
        f"warmup={settings.warmup_frames} baseline={settings.baseline_frames} "
        f"control_frames={settings.frames}"
    )
    if attempt.error:
        return f"{prefix}: failed {attempt.error}"
    return (
        f"{prefix}: max_relative={attempt.max_relative_rms_percent:.2f}% "
        f"max_rms={attempt.max_rms_kohm:.6f}kOhm "
        f"min_corr={attempt.min_correlation:.6f}"
    )


class DebugApp(tk.Tk):
    def __init__(self, demo: bool, port: str) -> None:
        super().__init__()
        self.title("Phase 3A ERT Hybrid Debug UI")
        self.geometry("1180x760")
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        acquisition = DemoAcquisition() if demo else SerialAcquisition()
        self.controller = DebugController(
            acquisition,
            progress=self._post_status,
            target_preview=self._post_target_preview,
        )
        self.demo = demo
        self._worker_active = False
        self._last_reconstructions: list[np.ndarray] = []
        self._last_self_test: selftest.SelfTestReport | None = None
        self._self_test_remedies: dict[str, selftest.CheckResult] = {}
        self._build_vars(port)
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._drain_events)

    def _build_vars(self, port: str) -> None:
        stored = load_settings(settings_path(UiSettings.default().log_dir))
        defaults = stored or UiSettings.default()
        self.restored_settings = stored is not None
        # An explicit --port always wins over whatever was stored.
        self.port_var = tk.StringVar(value=port)
        self.pattern_var = tk.StringVar(value=defaults.pattern)
        self.dac_var = tk.StringVar(value=str(defaults.dac))
        self.settle_var = tk.StringVar(value=str(defaults.settle_ms))
        self.samples_var = tk.StringVar(value=str(defaults.samples))
        self.warmup_var = tk.StringVar(value=str(defaults.warmup_frames))
        self.baseline_var = tk.StringVar(value=str(defaults.baseline_frames))
        self.target_warmup_var = tk.StringVar(value=str(defaults.target_warmup_frames))
        self.frames_var = tk.StringVar(value=str(defaults.frames))
        self.diameter_var = tk.StringVar(
            value="" if defaults.diameter_cm is None else str(defaults.diameter_cm)
        )
        self.command_var = tk.StringVar(value="")
        self.lenient_var = tk.BooleanVar(value=defaults.lenient_quality)
        self.allow_unstable_var = tk.BooleanVar(value=defaults.allow_unstable_baseline)
        self.filter_pairs_var = tk.BooleanVar(value=defaults.filter_pairs)
        self.electrode_offset_var = tk.StringVar(value=str(defaults.electrode_offset))
        self.electrode_reversed_var = tk.BooleanVar(value=defaults.electrode_reversed)
        self.self_test_frames_var = tk.StringVar(value=str(defaults.self_test_frames))
        self.expected_shunt_var = tk.StringVar(
            value="" if defaults.expected_shunt_ohms is None
            else str(defaults.expected_shunt_ohms)
        )
        self.status_var = tk.StringVar(value="Demo mode" if self.demo else "Disconnected")
        self.self_test_status_var = tk.StringVar(value="Not run")

    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=(10, 10, 4, 10))
        left.grid(row=0, column=0, sticky="ns")
        left.rowconfigure(0, weight=1)

        # Settings and actions scroll; the stop buttons are pinned underneath.
        # An emergency control that can scroll off screen is not a safety
        # control, and on a short window the old single-column pack layout put
        # both stop buttons past the bottom edge.
        canvas = tk.Canvas(left, width=214, highlightthickness=0, borderwidth=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        controls = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=controls, anchor="nw")
        controls.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
        )

        stop_frame = ttk.Frame(left, padding=(0, 8, 0, 0))
        stop_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

        right = ttk.Notebook(self)
        right.grid(row=0, column=1, sticky="nsew")

        self._build_controls(controls)
        self._build_stop_controls(stop_frame)
        self._build_tabs(right)
        self._bind_mousewheel(controls, canvas)
        self._bind_mousewheel(canvas, canvas)

    def _bind_mousewheel(self, widget: tk.Misc, canvas: tk.Canvas) -> None:
        """Wheel-scroll the control column without hijacking the whole window."""
        widget.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
        )
        for child in widget.winfo_children():
            self._bind_mousewheel(child, canvas)

    def _build_controls(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(parent, text="Connection").grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        ttk.Label(
            parent,
            textvariable=self.status_var,
            foreground="#444444",
            wraplength=200,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row += 1

        ttk.Label(parent, text="Port").grid(row=row, column=0, sticky="w")
        self.port_combo = ttk.Combobox(
            parent,
            textvariable=self.port_var,
            values=available_ports(),
            width=12,
        )
        self.port_combo.grid(row=row, column=1, sticky="ew", pady=1)
        row += 1
        ttk.Button(parent, text="Refresh ports", command=self.refresh_ports).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(2, 4)
        )
        row += 1

        ttk.Label(parent, text="Pattern").grid(row=row, column=0, sticky="w")
        ttk.Combobox(
            parent,
            textvariable=self.pattern_var,
            values=("adjacent", "opposite", "skip-1", "skip-2"),
            width=12,
            state="readonly",
        ).grid(row=row, column=1, sticky="ew", pady=1)
        row += 1

        for label, var in (
            ("DAC", self.dac_var),
            ("Settle ms", self.settle_var),
            ("Samples", self.samples_var),
            ("Warmup frames", self.warmup_var),
            ("Baseline frames", self.baseline_var),
            ("Target warmup", self.target_warmup_var),
            ("Run frames", self.frames_var),
            ("Diameter cm", self.diameter_var),
            ("Electrode offset", self.electrode_offset_var),
            ("Self test frames", self.self_test_frames_var),
            ("Fitted shunt ohm", self.expected_shunt_var),
        ):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(parent, textvariable=var, width=12).grid(
                row=row, column=1, sticky="ew", pady=1
            )
            row += 1

        ttk.Checkbutton(
            parent,
            text="Drop bad measurements",
            variable=self.lenient_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
        row += 1
        ttk.Checkbutton(
            parent,
            text="Allow unstable baseline",
            variable=self.allow_unstable_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        ttk.Checkbutton(
            parent,
            text="Substitute unstable pairs",
            variable=self.filter_pairs_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        ttk.Checkbutton(
            parent,
            text="Reversed electrode ring",
            variable=self.electrode_reversed_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
        row += 1

        for label, action in (
            ("Connect", self.connect),
            ("Self Test", self.run_self_test),
            ("Configure", self.configure),
            ("Probe Frame", self.probe_frame),
            ("Baseline", self.capture_baseline),
            ("Control Drift", self.capture_control),
            ("Tune Drift", self.tune_drift),
            ("Target Run", self.capture_target),
            ("Export Images", self.export_images),
        ):
            ttk.Button(parent, text=label, command=action).grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=2
            )
            row += 1

    def _build_stop_controls(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        tk.Button(
            parent,
            text="STOP / CURRENT IDLE",
            command=self.stop,
            bg="#b00020",
            fg="white",
            activebackground="#7f0018",
            activeforeground="white",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        tk.Button(
            parent,
            text="STOP EVERYTHING",
            command=self.stop_everything,
            bg="#000000",
            fg="white",
            activebackground="#333333",
            activeforeground="white",
        ).grid(row=1, column=0, sticky="ew")

    def _build_tabs(self, notebook: ttk.Notebook) -> None:
        reconstruction_tab = ttk.Frame(notebook)
        reconstruction_tab.columnconfigure(0, weight=1)
        reconstruction_tab.rowconfigure(0, weight=1)

        serial_tab = ttk.Frame(notebook)
        serial_tab.columnconfigure(0, weight=1)
        serial_tab.rowconfigure(0, weight=1)
        self.serial_text = tk.Text(serial_tab, height=10, wrap="word")
        self.serial_text.grid(row=0, column=0, columnspan=2, sticky="nsew")
        command_entry = ttk.Entry(serial_tab, textvariable=self.command_var)
        command_entry.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=4)
        command_entry.bind("<Return>", lambda _event: self.send_command())
        ttk.Button(serial_tab, text="Send", command=self.send_command).grid(
            row=1, column=1, pady=4
        )
        ttk.Label(
            serial_tab,
            text="Firmware commands: s ma ms mk mo el em eh pN tN cN nN jN.N g x i d ? h",
            foreground="#444444",
        ).grid(row=2, column=0, columnspan=2, sticky="w")

        self_test_tab = self._build_self_test_tab(notebook)

        self.health_text = tk.Text(notebook, height=10, wrap="word")
        self.files_text = tk.Text(notebook, height=10, wrap="word")

        self.figure, self.map_ax, self.vector_ax, self.scan_axes = build_reconstruction_figure()
        self.canvas = FigureCanvasTkAgg(self.figure, master=reconstruction_tab)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        status_frame = ttk.LabelFrame(reconstruction_tab, text="Live status stream", padding=(6, 4))
        status_frame.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
        status_frame.columnconfigure(0, weight=1)
        self.status_text = tk.Text(status_frame, height=6, wrap="word")
        self.status_text.grid(row=0, column=0, sticky="ew")
        status_scroll = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_text.yview)
        status_scroll.grid(row=0, column=1, sticky="ns")
        self.status_text.configure(yscrollcommand=status_scroll.set)

        for title, widget in zip(
            debug_tab_titles(),
            (reconstruction_tab, self_test_tab, self.health_text, serial_tab, self.files_text),
            strict=True,
        ):
            notebook.add(widget, text=title)

        self._append(self.status_text, "Ready.\n")
        if self.restored_settings:
            self._append(self.status_text, "Restored settings from previous session.\n")
        if self.demo:
            self._append(self.serial_text, "Demo acquisition selected; no serial port will be opened.\n")

    def _build_self_test_tab(self, notebook: ttk.Notebook) -> ttk.Frame:
        """One row per component check, worst-first ordering left to the report.

        A tree rather than a text log because the point of the tab is to answer
        "which component is broken" at a glance; a scrolling log makes the
        reader do the sorting.
        """
        tab = ttk.Frame(notebook)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        header = ttk.Frame(tab)
        header.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        header.columnconfigure(1, weight=1)
        ttk.Button(header, text="Run Self Test", command=self.run_self_test).grid(
            row=0, column=0, sticky="w"
        )
        self.self_test_status_label = ttk.Label(
            header,
            textvariable=self.self_test_status_var,
            wraplength=700,
        )
        self.self_test_status_label.grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Button(header, text="Save report", command=self.export_self_test).grid(
            row=0, column=2, sticky="e"
        )

        columns = ("status", "component", "check", "detail")
        self.self_test_tree = ttk.Treeview(
            tab, columns=columns, show="headings", height=18
        )
        for column, heading, width in (
            ("status", "Status", 60),
            ("component", "Component", 170),
            ("check", "Check", 250),
            ("detail", "Result", 520),
        ):
            self.self_test_tree.heading(column, text=heading)
            self.self_test_tree.column(column, width=width, anchor="w", stretch=(column == "detail"))
        self.self_test_tree.grid(row=1, column=0, sticky="nsew", padx=(6, 0))
        tree_scroll = ttk.Scrollbar(
            tab, orient="vertical", command=self.self_test_tree.yview
        )
        tree_scroll.grid(row=1, column=1, sticky="ns")
        self.self_test_tree.configure(yscrollcommand=tree_scroll.set)
        for status, color in SELF_TEST_STATUS_COLORS.items():
            self.self_test_tree.tag_configure(status.value, foreground=color)
        self.self_test_tree.bind("<<TreeviewSelect>>", self._show_self_test_remedy)

        remedy_frame = ttk.LabelFrame(tab, text="What to do", padding=(6, 4))
        remedy_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=6)
        remedy_frame.columnconfigure(0, weight=1)
        self.self_test_remedy = tk.Text(remedy_frame, height=4, wrap="word")
        self.self_test_remedy.grid(row=0, column=0, sticky="ew")
        self._append(
            self.self_test_remedy,
            "Select a row to see what a WARN or FAIL means and what to do about it.\n",
        )
        return tab

    def _render_self_test(self, report: selftest.SelfTestReport) -> None:
        self._last_self_test = report
        self.self_test_tree.delete(*self.self_test_tree.get_children())
        self._self_test_remedies = {}
        for index, result in enumerate(report.results):
            item = self.self_test_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    result.status.value,
                    result.component,
                    result.name,
                    result.detail,
                ),
                tags=(result.status.value,),
            )
            self._self_test_remedies[item] = result
        summary = format_self_test_summary(report)
        self.self_test_status_var.set(summary)
        self.self_test_status_label.configure(
            foreground=SELF_TEST_STATUS_COLORS[report.status]
        )
        self._append(self.status_text, f"{summary}\n")
        self._append(self.health_text, f"{selftest.format_report(report)}\n")
        blocker = report.first_blocker()
        if blocker is not None:
            self._show_result_remedy(blocker)

    def _show_self_test_remedy(self, _event=None) -> None:
        selection = self.self_test_tree.selection()
        if not selection:
            return
        result = self._self_test_remedies.get(selection[0])
        if result is not None:
            self._show_result_remedy(result)

    def _show_result_remedy(self, result: selftest.CheckResult) -> None:
        self.self_test_remedy.delete("1.0", "end")
        text = f"[{result.status.value}] {result.component} - {result.name}\n{result.detail}\n"
        if result.remedy:
            text += f"\n{result.remedy}\n"
        self._append(self.self_test_remedy, text)

    def export_self_test(self) -> Path | None:
        """Write the last report to a text file next to the run logs."""
        if self._last_self_test is None:
            self._append(self.status_text, "No self test to save yet.\n")
            return None
        try:
            settings = self.settings()
        except Exception:
            settings = UiSettings.default()
        directory = Path(settings.log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = directory / f"selftest-{stamp}.txt"
        try:
            path.write_text(
                selftest.format_report(self._last_self_test), encoding="utf-8"
            )
        except OSError as exc:
            self._append(self.status_text, f"Self test save failed: {exc}\n")
            return None
        self._append(self.files_text, f"Saved {path}\n")
        self._append(self.status_text, f"Saved {path}\n")
        return path

    def settings(self) -> UiSettings:
        diameter_text = self.diameter_var.get().strip()
        diameter = parse_float_field("diameter_cm", diameter_text, minimum=0.1) if diameter_text else None
        shunt_text = self.expected_shunt_var.get().strip()
        shunt = (
            parse_float_field("expected_shunt_ohms", shunt_text, minimum=0.1)
            if shunt_text else None
        )
        return UiSettings(
            port=self.port_var.get().strip(),
            pattern=self.pattern_var.get().strip(),
            dac=parse_int_field("dac", self.dac_var.get(), 0, 620),
            settle_ms=parse_int_field("settle_ms", self.settle_var.get(), 1, 10000),
            samples=parse_int_field("samples", self.samples_var.get(), 1, 1000),
            warmup_frames=parse_int_field("warmup_frames", self.warmup_var.get(), 0, 1000),
            baseline_frames=parse_int_field("baseline_frames", self.baseline_var.get(), 1, 1000),
            target_warmup_frames=parse_int_field(
                "target_warmup_frames", self.target_warmup_var.get(), 0, 1000
            ),
            frames=parse_int_field("frames", self.frames_var.get(), 1, 1000),
            diameter_cm=diameter,
            allow_unstable_baseline=bool(self.allow_unstable_var.get()),
            lenient_quality=bool(self.lenient_var.get()),
            filter_pairs=bool(self.filter_pairs_var.get()),
            electrode_offset=parse_int_field(
                "electrode_offset", self.electrode_offset_var.get(), 0, 11
            ),
            electrode_reversed=bool(self.electrode_reversed_var.get()),
            self_test_frames=parse_int_field(
                "self_test_frames", self.self_test_frames_var.get(), 2, 100
            ),
            expected_shunt_ohms=shunt,
        ).validate()

    def refresh_ports(self) -> None:
        ports = available_ports()
        self.port_combo.configure(values=ports)
        listing = ", ".join(ports) if ports else "none found"
        self._append(self.status_text, f"Serial ports: {listing}\n")

    def connect(self) -> None:
        self._run_with_settings("connect", self.controller.connect)

    def probe_frame(self) -> None:
        self._run_with_settings("probe", self.controller.probe_frame)

    def run_self_test(self) -> None:
        self.self_test_status_var.set("Running...")
        self._run_with_settings("self_test", self.controller.run_self_test)

    def configure(self) -> None:
        self._run_with_settings("configure", self.controller.configure)

    def capture_baseline(self) -> None:
        self._run_with_settings("baseline", self.controller.capture_baseline)

    def capture_control(self) -> None:
        self._run_with_settings("control", self.controller.capture_control)

    def tune_drift(self) -> None:
        self._run_with_settings("tune", self.controller.tune_drift)

    def capture_target(self) -> None:
        self._run_with_settings("target", self.controller.capture_target)

    def export_images(self) -> Path | None:
        """Write the on-screen figure plus a contact sheet of every scan.

        The on-screen figure only previews four scans, which is not enough to
        judge whether a target is reproducible across a run; the contact sheet
        renders all of them on one shared colour scale.
        """
        try:
            settings = self.settings()
        except Exception:
            settings = UiSettings.default()
        directory = Path(settings.log_dir) / "exports"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = directory / f"{stamp}_debug_ui.png"
        try:
            self.figure.savefig(path, dpi=140, bbox_inches="tight", facecolor="white")
        except Exception as exc:
            self._append(self.files_text, f"Export failed: {exc}\n")
            self._handle_error(f"export: {exc}")
            return None
        self._append(self.files_text, f"Exported {path}\n")
        self._append(self.status_text, f"Exported {path}\n")

        mesh = self.controller.mesh
        if self._last_reconstructions and mesh is not None:
            contact_path = directory / f"{stamp}_all_scans.png"
            average_path = directory / f"{stamp}_average.png"
            try:
                unified.save_reconstruction_images(
                    mesh,
                    self._last_reconstructions,
                    contact_path,
                    average_path,
                    settings.pattern,
                    settings.diameter_cm,
                )
            except Exception as exc:
                self._append(self.files_text, f"Contact sheet failed: {exc}\n")
            else:
                self._append(
                    self.files_text,
                    f"Exported {contact_path} ({len(self._last_reconstructions)} scans)\n"
                    f"Exported {average_path}\n",
                )
                self._append(self.status_text, f"Exported {contact_path}\n")
        return path

    def send_command(self) -> None:
        command = self.command_var.get().strip()
        if not command:
            return
        self._append(self.serial_text, f"> {command}\n")
        try:
            replies = self.controller.send_command(command)
        except Exception as exc:
            self._append(self.serial_text, f"ERROR {exc}\n")
            return
        for line in replies or ["(no reply)"]:
            self._append(self.serial_text, f"{line}\n")
        self.command_var.set("")

    def stop_everything(self) -> None:
        """Force current idle and drop the port, whatever state the UI is in."""
        try:
            errors = self.controller.emergency_stop()
        except Exception as exc:
            self.status_var.set("Emergency stop error")
            self._handle_error(f"stop everything: {exc}")
            return
        # Clear the busy flag unconditionally: the port is closed, so a worker
        # still unwinding cannot do anything further, and leaving the flag set
        # would lock every button.
        self._worker_active = False
        self.status_var.set("EVERYTHING STOPPED / DISCONNECTED")
        self._append(
            self.status_text,
            "STOP EVERYTHING: DAC idle, muxes disabled, port closed. Reconnect to continue.\n",
        )
        for error in errors:
            self._append(self.status_text, f"  stop-everything warning: {error}\n")

    def stop(self) -> None:
        worker_was_active = self._worker_active
        try:
            self.controller.stop()
        except Exception as exc:
            self.status_var.set("Stop error")
            self._handle_error(f"stop: {exc}")
            return
        if worker_was_active:
            self.status_var.set("STOP requested")
            self._append(
                self.status_text,
                "STOP requested; waiting for active capture to finish...\n",
            )
        else:
            self.status_var.set("STOPPED / CURRENT IDLE")
            self._append(self.status_text, "STOP / CURRENT IDLE sent.\n")

    def _run_with_settings(self, name: str, action: Callable[[UiSettings], Any]) -> None:
        try:
            settings = self.settings()
        except Exception as exc:
            self._handle_error(f"{name}: {exc}")
            return
        self._run_worker(name, lambda: action(settings))

    def _run_worker(self, name: str, fn: Callable[[], Any]) -> None:
        if self._worker_active:
            self._append(
                self.status_text,
                f"{name} skipped: active capture still finishing.\n",
            )
            return
        self._worker_active = True
        self.status_var.set(f"{name} running")
        self._append(self.status_text, f"{name} started.\n")

        def worker() -> None:
            try:
                result = fn()
            except CaptureStopped as exc:
                self.events.put(("stopped", (name, exc.partial)))
            except Exception as exc:
                self.events.put(("error", f"{name}: {exc}"))
            else:
                self.events.put((name, result))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event, payload)
        self.after(100, self._drain_events)

    def _handle_event(self, event: str, payload: object) -> None:
        if event == "status":
            self._append(self.status_text, f"{payload}\n")
            return
        if event == "target_preview":
            self._draw_reconstructions(payload)
            return

        self._worker_active = False
        if event == "error":
            self.status_var.set("Error")
            self._handle_error(str(payload))
            return
        if event == "stopped":
            name, partial = payload
            self._handle_stopped(name, partial)
            return
        if event == "configure":
            self._save_current_settings()

        if event in {"baseline", "control", "target"} and "stopped" in str(payload).lower():
            self.status_var.set("STOPPED / CURRENT IDLE")
        else:
            self.status_var.set(f"{event} complete")
        self._append(self.status_text, f"{event} complete.\n")
        if event == "self_test":
            self._render_self_test(payload)
        elif event == "probe":
            summary = format_frame_diagnostics(payload)
            self._append(self.status_text, f"{summary}\n")
            self._append(self.health_text, f"{summary}\n")
        elif event == "baseline":
            self._draw_baseline_reference(payload.baseline)
            self._append(self.health_text, f"Baseline: {payload.stability}\n")
        elif event == "control":
            summary = format_control_drift_summary(payload)
            self._append(self.status_text, f"{summary}\n")
            self._append(self.health_text, f"{summary}\n")
        elif event == "tune":
            self._handle_tune_result(payload)
        elif event == "target":
            self._draw_reconstructions(payload.reconstructions, payload.frame_healths)
            self._append(self.health_text, f"Target frames: {len(payload.reconstructions)}\n")

    def _handle_stopped(self, name: str, partial: object) -> None:
        self.status_var.set("STOPPED / CURRENT IDLE")
        kept = describe_partial_capture(partial)
        self._append(self.status_text, f"{name} stopped; {kept}\n")
        self._append(self.health_text, f"{name} stopped; {kept}\n")
        if isinstance(partial, TargetResult) and partial.reconstructions:
            self._draw_reconstructions(partial.reconstructions, partial.frame_healths)

    def _save_current_settings(self) -> None:
        try:
            settings = self.settings()
            save_settings(settings, settings_path(settings.log_dir))
        except Exception as exc:
            self._append(self.status_text, f"Could not save settings: {exc}\n")

    def _handle_error(self, message: str) -> None:
        self._append(self.status_text, f"ERROR {message}\n")
        messagebox.showerror("ERT UI Error", message)

    def _handle_tune_result(self, result: DriftTuneResult) -> None:
        summary = format_drift_tune_summary(result)
        self._append(self.status_text, f"{summary}\n")
        self._append(self.health_text, f"{summary}\n")
        for attempt in result.attempts:
            self._append(self.health_text, f"{format_drift_tune_attempt(attempt)}\n")
        if result.best is not None:
            self._apply_settings_to_fields(result.best.settings)

    def _apply_settings_to_fields(self, settings: UiSettings) -> None:
        self.settle_var.set(str(settings.settle_ms))
        self.samples_var.set(str(settings.samples))
        self.warmup_var.set(str(settings.warmup_frames))
        self.baseline_var.set(str(settings.baseline_frames))
        self.frames_var.set(str(settings.frames))

    def _draw_reconstructions(
        self,
        reconstructions: list[np.ndarray],
        frame_healths: list[unified.FrameHealthScore] | None = None,
    ) -> None:
        self._last_reconstructions = list(reconstructions)
        latest = latest_reconstruction(reconstructions)
        self._draw_latest_map(latest, len(reconstructions))
        self._draw_latest_vector(latest, len(reconstructions))
        self._draw_scan_previews(reconstructions)
        self._annotate_substituted_pairs(frame_healths)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _annotate_substituted_pairs(
        self,
        frame_healths: list[unified.FrameHealthScore] | None,
    ) -> None:
        """Show how much of the latest scan was substituted, not measured.

        The best-effort filter writes the baseline value into dropped pairs,
        which asserts "nothing changed here" to the solver and biases the image
        toward a clean null result. Rendering the fraction on the figure keeps a
        substituted null from being read as a measured one (validity-audit
        D-05).
        """
        if not frame_healths:
            return
        health = frame_healths[-1]
        total = health.kept_pairs + health.dropped_pairs
        if not total or not health.dropped_pairs:
            return
        percent = 100.0 * health.dropped_pairs / total
        self.map_ax.text(
            0.5,
            -0.06,
            f"{health.dropped_pairs}/{total} pairs ({percent:.0f}%) substituted "
            f"from baseline, not measured - {health.quality_label}",
            transform=self.map_ax.transAxes,
            ha="center",
            va="top",
            fontsize=7,
            color="#b00020",
        )

    def _draw_baseline_reference(self, baseline: np.ndarray) -> None:
        self.map_ax.clear()
        self.map_ax.set_title("Baseline reference")
        self.map_ax.set_aspect("equal")
        self.map_ax.set_axis_off()
        self.map_ax.text(
            0.5,
            0.5,
            "Baseline vs itself = zero difference\nUse this as reference, not target image",
            ha="center",
            va="center",
            transform=self.map_ax.transAxes,
        )
        self.vector_ax.clear()
        self.vector_ax.set_title("Baseline measurement vector")
        self.vector_ax.set_xlabel("Measurement index")
        self.vector_ax.set_ylabel("Transfer resistance")
        if baseline.size:
            self.vector_ax.plot(baseline)
            self.vector_ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.5)
        else:
            self.vector_ax.text(0.5, 0.5, "No baseline data", ha="center", va="center")
        for axis in self.scan_axes:
            axis.clear()
            axis.set_axis_off()
            axis.text(0.5, 0.5, "Run target\nto compare scans", ha="center", va="center")
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _draw_latest_map(self, latest: np.ndarray, scan_count: int) -> None:
        self.map_ax.clear()
        title = f"Latest scan map (scan {scan_count})" if scan_count else "Latest scan map"
        self.map_ax.set_title(title)
        self.map_ax.set_aspect("equal")
        self.map_ax.set_axis_off()
        mesh = self.controller.mesh
        if latest.size == 0:
            self.map_ax.text(0.5, 0.5, "No reconstruction data", ha="center", va="center")
            return
        if mesh is None or len(latest) != len(mesh.element):
            self.map_ax.text(0.5, 0.5, "Map unavailable", ha="center", va="center")
            return
        limit = max(float(np.max(np.abs(latest))), np.finfo(float).eps)
        self.map_ax.tripcolor(
            mesh.node[:, 0],
            mesh.node[:, 1],
            mesh.element,
            latest,
            shading="flat",
            cmap="coolwarm",
            vmin=-limit,
            vmax=limit,
        )
        self._label_electrodes(self.map_ax, mesh)

    @staticmethod
    def _label_electrodes(axis, mesh) -> None:
        """Label electrodes from the mesh's own positions (validity-audit D-01)."""
        for index, x, y in base.electrode_label_positions(mesh, N_ELECTRODES):
            axis.text(
                x,
                y,
                f"E{index + 1}",
                ha="center",
                va="center",
                fontsize=7,
                fontweight="bold",
            )

    def _draw_latest_vector(self, latest: np.ndarray, scan_count: int) -> None:
        self.vector_ax.clear()
        title = (
            f"Latest reconstruction vector (scan {scan_count})"
            if scan_count
            else "Latest reconstruction vector"
        )
        self.vector_ax.set_title(title)
        self.vector_ax.set_xlabel("Vector index")
        self.vector_ax.set_ylabel("Difference")
        if latest.size:
            self.vector_ax.plot(latest)
            self.vector_ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.5)
        else:
            self.vector_ax.text(0.5, 0.5, "No reconstruction data", ha="center", va="center")

    def _draw_scan_previews(self, reconstructions: list[np.ndarray]) -> None:
        indices = preview_scan_indices(len(reconstructions), len(self.scan_axes))
        values = [reconstructions[index] for index in indices]
        limit = max(
            [float(np.max(np.abs(value))) for value in values if value.size] or [np.finfo(float).eps],
        )
        mesh = self.controller.mesh
        for preview_position, axis in enumerate(self.scan_axes):
            axis.clear()
            axis.set_axis_off()
            # Without this the previews render as ellipses, which misreads as a
            # distorted reconstruction rather than a distorted axis.
            axis.set_aspect("equal")
            if preview_position >= len(indices):
                axis.set_title("Scan")
                axis.text(0.5, 0.5, "No scan", ha="center", va="center")
                continue
            scan_index = indices[preview_position]
            value = reconstructions[scan_index]
            axis.set_title(f"Scan {scan_index + 1}")
            if mesh is None or len(value) != len(mesh.element):
                axis.text(0.5, 0.5, "Map unavailable", ha="center", va="center")
                continue
            axis.tripcolor(
                mesh.node[:, 0],
                mesh.node[:, 1],
                mesh.element,
                value,
                shading="flat",
                cmap="coolwarm",
                vmin=-limit,
                vmax=limit,
            )

    def _on_close(self) -> None:
        self._save_current_settings()
        try:
            self.controller.close()
        except Exception as exc:
            self._append(self.status_text, f"ERROR close: {exc}\n")
        self.destroy()

    @staticmethod
    def _append(widget: tk.Text, text: str) -> None:
        widget.insert("end", text)
        widget.see("end")

    def _post_status(self, message: str) -> None:
        self.events.put(("status", message))

    def _post_target_preview(self, reconstructions: list[np.ndarray]) -> None:
        self.events.put(("target_preview", reconstructions))


def run_app(demo: bool = False, port: str = "COM3") -> None:
    app = DebugApp(demo=demo, port=port)
    app.mainloop()
