"""
Offline analyzer for ERT exports.

Loads CSV/NPZ exports from ert.py, summarizes stability and channel changes,
and prepares measurement matrices for later PyEIT experiments without claiming
full reconstruction from current hardware.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


@dataclass(frozen=True)
class LoadedExport:
    source: Path
    channels: tuple[str, ...]
    timestamps: tuple[str, ...]
    measurements: np.ndarray
    delta: np.ndarray
    baseline: np.ndarray


@dataclass(frozen=True)
class ExportSummary:
    scan_count: int
    channel_count: int
    delta_mean: np.ndarray
    delta_std: np.ndarray
    delta_min: np.ndarray
    delta_max: np.ndarray


def load_export(path: Path) -> LoadedExport:
    if path.suffix.lower() == ".npz":
        return load_npz_export(path)
    if path.suffix.lower() == ".csv":
        return load_csv_export(path)
    raise ValueError(f"Unsupported export format: {path.suffix}")


def load_npz_export(path: Path) -> LoadedExport:
    with np.load(path, allow_pickle=False) as data:
        measurements = np.asarray(data["measurements"], dtype=float)
        delta = np.asarray(data["delta"], dtype=float)
        baseline = np.asarray(data["baseline"], dtype=float)
        channels = tuple(str(value) for value in data["channels"].tolist())
        timestamps = tuple(str(value) for value in data["timestamps"].tolist())
    return LoadedExport(
        source=path,
        channels=channels,
        timestamps=timestamps,
        measurements=measurements,
        delta=delta,
        baseline=baseline,
    )


def load_csv_export(path: Path) -> LoadedExport:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        channel_names = tuple(column[:-3] for column in header[1:] if column.endswith("_mv") and not column.endswith("_delta_mv"))
        measurement_width = len(channel_names)
        timestamps: list[str] = []
        measurements: list[list[float]] = []
        delta_rows: list[list[float]] = []

        for row in reader:
            if not row:
                continue
            timestamps.append(row[0])
            measurements.append([float(value) for value in row[1 : 1 + measurement_width]])
            delta_rows.append([float(value) for value in row[1 + measurement_width : 1 + measurement_width * 2]])

    measurement_array = np.asarray(measurements, dtype=float)
    delta_array = np.asarray(delta_rows, dtype=float)
    baseline_row = measurement_array[0] - delta_array[0] if len(measurement_array) else np.empty((0,), dtype=float)
    baseline = np.tile(baseline_row, (measurement_array.shape[0], 1)) if measurement_array.size else np.empty((0, 0), dtype=float)
    return LoadedExport(
        source=path,
        channels=channel_names,
        timestamps=tuple(timestamps),
        measurements=measurement_array,
        delta=delta_array,
        baseline=baseline,
    )


def summarize_export(export: LoadedExport) -> ExportSummary:
    return ExportSummary(
        scan_count=int(export.measurements.shape[0]),
        channel_count=int(export.measurements.shape[1]) if export.measurements.ndim == 2 else 0,
        delta_mean=np.mean(export.delta, axis=0),
        delta_std=np.std(export.delta, axis=0),
        delta_min=np.min(export.delta, axis=0),
        delta_max=np.max(export.delta, axis=0),
    )


def build_measurement_matrix(export: LoadedExport) -> np.ndarray:
    return np.asarray(export.measurements, dtype=float)


def print_summary(summary: ExportSummary, channels: tuple[str, ...]) -> None:
    print(f"Scans: {summary.scan_count}")
    print(f"Channels: {summary.channel_count}")
    print()
    print("Per-electrode delta summary:")
    for index, channel in enumerate(channels):
        print(
            f"{channel}: mean {summary.delta_mean[index]:+.2f} mV | "
            f"std {summary.delta_std[index]:.2f} | "
            f"min {summary.delta_min[index]:+.2f} | "
            f"max {summary.delta_max[index]:+.2f}"
        )


def plot_export(export: LoadedExport, summary: ExportSummary) -> None:
    channels = list(export.channels)
    latest_measurement = export.measurements[-1]
    latest_delta = export.delta[-1]
    baseline = export.baseline[-1] if len(export.baseline) else np.zeros_like(latest_measurement)

    fig = plt.figure(figsize=(14, 8))
    grid = fig.add_gridspec(2, 2, height_ratios=(2, 1.2))
    ax_delta = fig.add_subplot(grid[0, 0])
    ax_absolute = fig.add_subplot(grid[0, 1])
    ax_history = fig.add_subplot(grid[1, :])

    ax_delta.set_title("Latest Delta", fontweight="bold")
    colors = ["red" if value > 0 else "blue" for value in latest_delta]
    ax_delta.bar(channels, latest_delta, color=colors, alpha=0.75)
    ax_delta.axhline(y=0, color="black", linestyle="--", linewidth=1)
    ax_delta.set_ylabel("Change (mV)")
    ax_delta.grid(True, alpha=0.3)

    ax_absolute.set_title("Baseline vs Latest", fontweight="bold")
    x = np.arange(len(channels))
    width = 0.35
    ax_absolute.bar(x - width / 2, baseline, width, label="Baseline", alpha=0.7)
    ax_absolute.bar(x + width / 2, latest_measurement, width, label="Latest", alpha=0.7)
    ax_absolute.set_ylabel("Voltage (mV)")
    ax_absolute.set_xticks(x)
    ax_absolute.set_xticklabels(channels)
    ax_absolute.legend()
    ax_absolute.grid(True, alpha=0.3)

    color_limit = max(float(np.max(np.abs(export.delta))), 1.0)
    image = ax_history.imshow(
        export.delta[-20:],
        aspect="auto",
        cmap="coolwarm",
        vmin=-color_limit,
        vmax=color_limit,
        interpolation="nearest",
    )
    ax_history.set_title("Delta History", fontweight="bold")
    ax_history.set_xticks(np.arange(len(channels)))
    ax_history.set_xticklabels(channels)
    ax_history.set_ylabel("Recent Scans")
    ax_history.set_xlabel("Electrode")
    colorbar = fig.colorbar(image, ax=ax_history, pad=0.02)
    colorbar.set_label("Delta (mV)")

    fig.suptitle(
        f"{export.source.name} | scans={summary.scan_count} | channels={summary.channel_count}",
        fontweight="bold",
    )
    plt.tight_layout()
    plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze ERT exports and prepare matrices for later PyEIT use."
    )
    parser.add_argument("export_path", help="Path to .npz or .csv export from ert.py")
    parser.add_argument("--no-plot", action="store_true", help="Print summary only")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export = load_export(Path(args.export_path))
    summary = summarize_export(export)
    print_summary(summary, export.channels)
    matrix = build_measurement_matrix(export)
    print()
    print(f"Measurement matrix shape: {matrix.shape}")
    print("Note: matrix useful for later PyEIT experiments, not full reconstruction with current hardware.")
    if not args.no_plot:
        plot_export(export, summary)


if __name__ == "__main__":
    main()
