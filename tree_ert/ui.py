from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk
from typing import Any

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import phase3a_reconstruct as base
import phase3a_unified_reconstruct as unified
from phase3a_reconstruct import N_ELECTRODES
from tree_ert.acquisition import DemoAcquisition, SerialAcquisition
from tree_ert.controller import DebugController, DriftTuneAttempt, DriftTuneResult
from tree_ert.settings import UiSettings, parse_float_field, parse_int_field


def average_reconstruction_vector(reconstructions: list[np.ndarray]) -> np.ndarray:
    if not reconstructions:
        return np.asarray([], dtype=float)
    return np.mean(np.stack(reconstructions), axis=0)


def build_reconstruction_figure() -> tuple[Figure, object, object, tuple[object, ...]]:
    figure = Figure(figsize=(10, 6.5), dpi=100)
    grid = figure.add_gridspec(2, 4, height_ratios=(3.0, 1.15))
    map_ax = figure.add_subplot(grid[0, 0:2])
    vector_ax = figure.add_subplot(grid[0, 2:4])
    scan_axes = tuple(figure.add_subplot(grid[1, index]) for index in range(4))
    map_ax.set_title("Average 2D map")
    map_ax.set_aspect("equal")
    map_ax.set_axis_off()
    vector_ax.set_title("Average reconstruction vector")
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
    return ("Reconstruction", "Health", "Serial", "Files")


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
        self._build_vars(port)
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._drain_events)

    def _build_vars(self, port: str) -> None:
        defaults = UiSettings.default()
        self.port_var = tk.StringVar(value=port)
        self.pattern_var = tk.StringVar(value=defaults.pattern)
        self.dac_var = tk.StringVar(value=str(defaults.dac))
        self.settle_var = tk.StringVar(value=str(defaults.settle_ms))
        self.samples_var = tk.StringVar(value=str(defaults.samples))
        self.warmup_var = tk.StringVar(value=str(defaults.warmup_frames))
        self.baseline_var = tk.StringVar(value=str(defaults.baseline_frames))
        self.frames_var = tk.StringVar(value=str(defaults.frames))
        self.diameter_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Demo mode" if self.demo else "Disconnected")

    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=10)
        left.grid(row=0, column=0, sticky="ns")
        right = ttk.Notebook(self)
        right.grid(row=0, column=1, sticky="nsew")

        self._build_controls(left)
        self._build_tabs(right)

    def _build_controls(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Connection").pack(anchor="w")
        ttk.Label(parent, textvariable=self.status_var, foreground="#444444").pack(anchor="w", pady=(0, 8))
        ttk.Entry(parent, textvariable=self.port_var, width=18).pack(fill="x", pady=2)
        ttk.Combobox(
            parent,
            textvariable=self.pattern_var,
            values=("adjacent", "opposite", "skip-1", "skip-2"),
            width=16,
            state="readonly",
        ).pack(fill="x", pady=2)

        for label, var in (
            ("DAC", self.dac_var),
            ("Settle ms", self.settle_var),
            ("Samples", self.samples_var),
            ("Warmup frames", self.warmup_var),
            ("Baseline frames", self.baseline_var),
            ("Run frames", self.frames_var),
            ("Diameter cm", self.diameter_var),
        ):
            ttk.Label(parent, text=label).pack(anchor="w", pady=(8, 0))
            ttk.Entry(parent, textvariable=var, width=18).pack(fill="x", pady=2)

        for label, action in (
            ("Connect", self.connect),
            ("Configure", self.configure),
            ("Baseline", self.capture_baseline),
            ("Control Drift", self.capture_control),
            ("Tune Drift", self.tune_drift),
            ("Target Run", self.capture_target),
            ("Export", self.export_placeholder),
        ):
            ttk.Button(parent, text=label, command=action).pack(fill="x", pady=4)

        tk.Button(
            parent,
            text="STOP / CURRENT IDLE",
            command=self.stop,
            bg="#b00020",
            fg="white",
            activebackground="#7f0018",
            activeforeground="white",
        ).pack(fill="x", pady=12)

    def _build_tabs(self, notebook: ttk.Notebook) -> None:
        reconstruction_tab = ttk.Frame(notebook)
        reconstruction_tab.columnconfigure(0, weight=1)
        reconstruction_tab.rowconfigure(0, weight=1)

        self.serial_text = tk.Text(notebook, height=10, wrap="word")
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
            (reconstruction_tab, self.health_text, self.serial_text, self.files_text),
            strict=True,
        ):
            notebook.add(widget, text=title)

        self._append(self.status_text, "Ready.\n")
        if self.demo:
            self._append(self.serial_text, "Demo acquisition selected; no serial port will be opened.\n")

    def settings(self) -> UiSettings:
        diameter_text = self.diameter_var.get().strip()
        diameter = parse_float_field("diameter_cm", diameter_text, minimum=0.1) if diameter_text else None
        return UiSettings(
            port=self.port_var.get().strip(),
            pattern=self.pattern_var.get().strip(),
            dac=parse_int_field("dac", self.dac_var.get(), 0, 620),
            settle_ms=parse_int_field("settle_ms", self.settle_var.get(), 1, 10000),
            samples=parse_int_field("samples", self.samples_var.get(), 1, 1000),
            warmup_frames=parse_int_field("warmup_frames", self.warmup_var.get(), 0, 1000),
            baseline_frames=parse_int_field("baseline_frames", self.baseline_var.get(), 1, 1000),
            frames=parse_int_field("frames", self.frames_var.get(), 1, 1000),
            diameter_cm=diameter,
        ).validate()

    def connect(self) -> None:
        self._run_with_settings("connect", self.controller.connect)

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

    def export_placeholder(self) -> None:
        self._append(self.files_text, "Export uses phase3a_logs outputs from capture runs.\n")

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
            self._draw_average(payload)
            return

        self._worker_active = False
        if event == "error":
            self.status_var.set("Error")
            self._handle_error(str(payload))
            return

        if event in {"baseline", "control", "target"} and "stopped" in str(payload).lower():
            self.status_var.set("STOPPED / CURRENT IDLE")
        else:
            self.status_var.set(f"{event} complete")
        self._append(self.status_text, f"{event} complete.\n")
        if event == "baseline":
            self._draw_baseline_reference(payload.baseline)
            self._append(self.health_text, f"Baseline: {payload.stability}\n")
        elif event == "control":
            summary = format_control_drift_summary(payload)
            self._append(self.status_text, f"{summary}\n")
            self._append(self.health_text, f"{summary}\n")
        elif event == "tune":
            self._handle_tune_result(payload)
        elif event == "target":
            self._draw_average(payload.reconstructions)
            self._append(self.health_text, f"Target frames: {len(payload.reconstructions)}\n")

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

    def _draw_average(self, reconstructions: list[np.ndarray]) -> None:
        average = average_reconstruction_vector(reconstructions)
        self._draw_average_map(average)
        self._draw_average_vector(average)
        self._draw_scan_previews(reconstructions)
        self.figure.tight_layout()
        self.canvas.draw_idle()

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

    def _draw_average_map(self, average: np.ndarray) -> None:
        self.map_ax.clear()
        self.map_ax.set_title("Average 2D map")
        self.map_ax.set_aspect("equal")
        self.map_ax.set_axis_off()
        mesh = self.controller.mesh
        if average.size == 0:
            self.map_ax.text(0.5, 0.5, "No reconstruction data", ha="center", va="center")
            return
        if mesh is None or len(average) != len(mesh.element):
            self.map_ax.text(0.5, 0.5, "Map unavailable", ha="center", va="center")
            return
        limit = max(float(np.max(np.abs(average))), np.finfo(float).eps)
        self.map_ax.tripcolor(
            mesh.node[:, 0],
            mesh.node[:, 1],
            mesh.element,
            average,
            shading="flat",
            cmap="coolwarm",
            vmin=-limit,
            vmax=limit,
        )
        for index in range(N_ELECTRODES):
            angle = 2.0 * np.pi * index / N_ELECTRODES
            self.map_ax.text(
                1.12 * np.cos(angle),
                1.12 * np.sin(angle),
                f"E{index + 1}",
                ha="center",
                va="center",
                fontsize=7,
                fontweight="bold",
            )

    def _draw_average_vector(self, average: np.ndarray) -> None:
        self.vector_ax.clear()
        self.vector_ax.set_title("Average reconstruction vector")
        self.vector_ax.set_xlabel("Vector index")
        self.vector_ax.set_ylabel("Difference")
        if average.size:
            self.vector_ax.plot(average)
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
