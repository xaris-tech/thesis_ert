"""Dummy-load sweep: measure the current source's output impedance.

The pass condition for a current source is that the delivered current does not
depend on the load. Before the 2026-09-02 repair (ADR-0014) this rig's current
tracked 1/R_load, which is what a voltage source does; the repair restored the
current-sense feedback, and this tool is the measurement that says whether the
correction was sufficient. It is also the discriminating test for the 213 uA
offset at zero command recorded in docs/i-sat-investigation-2026-09-02.md
section 10.4: with the electrodes disconnected and a resistor in their place, a
near-zero reading at DAC code 0 implicates the electrodes and a reading near
213 uA implicates the circuit.

Two subcommands, because the load is changed by hand and the fit needs several
loads:

    measure  one resistor, several DAC codes, appended to a CSV
    fit      read that CSV back and solve for Rout

Run measure once per resistor with the same --out file, then run fit.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from tree_ert.settings import CURRENT_RANGES

CSV_FIELDS = ("load_ohms", "dac_code", "repeat", "voltage_mv", "current_ua", "quality")


@dataclass(frozen=True)
class HoldReading:
    """One HOLD record: the instrument's own reading of a held drive pair."""

    dac_code: int
    voltage_mv: float
    current_ua: float
    quality: str


@dataclass(frozen=True)
class SourceFit:
    """Thevenin fit of one DAC code across loads.

    flatness_percent is the headline number: peak-to-peak current spread as a
    percentage of the mean. A current source is flat; the pre-repair rig was not.
    """

    dac_code: int
    thevenin_mv: float
    output_ohms: float
    flatness_percent: float
    points: int


def parse_hold_line(line: str) -> HoldReading | None:
    """Parse one firmware HOLD line, or None for anything else.

    Returns None rather than raising so the caller can feed it every line the
    firmware prints - the d command also emits two human-readable [DEBUG] lines,
    and a board mid-boot emits more.
    """
    text = line.strip()
    if not text.startswith("HOLD,"):
        return None
    parts = text.split(",")
    if len(parts) < 2 or parts[1] != "1":
        raise ValueError(f"unsupported HOLD version in {text!r}")
    fields = dict(zip(parts[2::2], parts[3::2]))
    missing = {"DAC", "V", "I", "Q"} - fields.keys()
    if missing:
        raise ValueError(f"HOLD line missing {sorted(missing)}: {text!r}")
    return HoldReading(
        dac_code=int(fields["DAC"]),
        voltage_mv=float(fields["V"]),
        current_ua=float(fields["I"]),
        quality=fields["Q"],
    )


def fit_source(load_ohms: list[float], current_ua: list[float]) -> SourceFit:
    """Solve I = Vth / (Rout + Rload) for Vth and Rout by least squares.

    Linearised as 1/I = Rload/Vth + Rout/Vth, so a straight line through
    (Rload, 1/I) has slope 1/Vth and intercept Rout/Vth. Needs at least two
    distinct loads; a perfectly flat source gives a slope of zero, which is the
    ideal case and is reported as an infinite output impedance rather than
    treated as an error.
    """
    if len(load_ohms) != len(current_ua):
        raise ValueError("load and current series must be the same length")
    if len(set(load_ohms)) < 2:
        raise ValueError("need at least two distinct loads to fit output impedance")
    if any(value == 0.0 for value in current_ua):
        raise ValueError("cannot fit through a zero-current point")

    inverse = [1.0 / (value * 1e-6) for value in current_ua]  # 1/A, from uA
    mean_r = statistics.fmean(load_ohms)
    mean_inv = statistics.fmean(inverse)
    covariance = sum(
        (r - mean_r) * (inv - mean_inv) for r, inv in zip(load_ohms, inverse)
    )
    variance = sum((r - mean_r) ** 2 for r in load_ohms)
    slope = covariance / variance
    intercept = mean_inv - slope * mean_r

    if slope <= 0.0:
        thevenin_mv = float("inf")
        output_ohms = float("inf")
    else:
        thevenin_mv = (1.0 / slope) * 1000.0  # V to mV
        output_ohms = intercept / slope

    spread = max(current_ua) - min(current_ua)
    mean_current = statistics.fmean(current_ua)
    flatness = abs(spread / mean_current) * 100.0 if mean_current else float("inf")
    return SourceFit(
        dac_code=0,
        thevenin_mv=thevenin_mv,
        output_ohms=output_ohms,
        flatness_percent=flatness,
        points=len(load_ohms),
    )


def fit_by_dac_code(rows: list[dict]) -> list[SourceFit]:
    """Group measured rows by DAC code and fit each group separately."""
    grouped: dict[int, list[tuple[float, float]]] = {}
    for row in rows:
        code = int(row["dac_code"])
        grouped.setdefault(code, []).append(
            (float(row["load_ohms"]), float(row["current_ua"]))
        )
    fits = []
    for code in sorted(grouped):
        points = grouped[code]
        if len({load for load, _ in points}) < 2:
            continue
        loads = [load for load, _ in points]
        currents = [current for _, current in points]
        fit = fit_source(loads, currents)
        fits.append(
            SourceFit(
                dac_code=code,
                thevenin_mv=fit.thevenin_mv,
                output_ohms=fit.output_ohms,
                flatness_percent=fit.flatness_percent,
                points=fit.points,
            )
        )
    return fits


def format_fit_report(fits: list[SourceFit]) -> str:
    """Human-readable summary. Verdict is per DAC code, not overall.

    A single flatness threshold is deliberately not baked in here: what counts
    as adequate depends on the spread of load impedances the tree actually
    presents, which is not yet characterised (ADR-0003's report-not-gate rule).
    """
    if not fits:
        return "No DAC code was measured at two or more distinct loads; nothing to fit."
    lines = [
        f"{'DAC':>5} {'Vth (mV)':>10} {'Rout (ohm)':>12} "
        f"{'flatness %':>11} {'loads':>6}",
    ]
    for fit in fits:
        lines.append(
            f"{fit.dac_code:>5} {fit.thevenin_mv:>10.1f} {fit.output_ohms:>12.1f} "
            f"{fit.flatness_percent:>11.1f} {fit.points:>6}"
        )
    lines.append("")
    lines.append(
        "Flatness is peak-to-peak current spread over the mean. A current source "
        "is flat across loads; before the ADR-0014 repair this rig tracked "
        "1/R_load. Rout well above the load range is the same statement."
    )
    return "\n".join(lines)


def read_hold(ser, timeout: float = 4.0) -> HoldReading:
    """Send d and return the HOLD record it prints.

    The muxes stay enabled after this returns, by design - the operator may want
    a multimeter on the same held state.
    """
    ser.write(b"d\n")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            continue
        reading = parse_hold_line(raw.decode(errors="ignore"))
        if reading is not None:
            return reading
    raise TimeoutError(
        "no HOLD line within timeout; the flashed firmware may predate it "
        "(reflash the unified .ino)"
    )


def measure(args: argparse.Namespace) -> int:
    import serial  # imported here so fit works with no pyserial installed

    codes = [int(code) for code in args.codes.split(",")]
    ceiling = CURRENT_RANGES[args.current_range][2]
    over = [code for code in codes if code < 0 or code > ceiling]
    if over:
        raise SystemExit(
            f"DAC codes {over} are outside 0..{ceiling} on the "
            f"{args.current_range} range"
        )

    print(f"Load {args.load_ohms:g} ohm, range {args.current_range}, codes {codes}")
    print("Electrodes must be disconnected and the resistor fitted across E1-E2.")
    rows = []
    with serial.Serial(args.port, args.baud, timeout=1.0) as ser:
        time.sleep(2.0)  # the ESP32-S3 resets when the port opens
        ser.reset_input_buffer()
        ser.write((CURRENT_RANGES[args.current_range][0] + "\n").encode())
        ser.write(f"n{args.samples}\n".encode())
        time.sleep(0.3)
        ser.reset_input_buffer()
        try:
            for code in codes:
                ser.write(f"p{code}\n".encode())
                time.sleep(0.2)
                ser.reset_input_buffer()
                for repeat in range(args.repeat):
                    reading = read_hold(ser)
                    rows.append({
                        "load_ohms": args.load_ohms,
                        "dac_code": reading.dac_code,
                        "repeat": repeat,
                        "voltage_mv": reading.voltage_mv,
                        "current_ua": reading.current_ua,
                        "quality": reading.quality,
                    })
                    print(
                        f"  code {reading.dac_code:>4}  "
                        f"I {reading.current_ua:>9.3f} uA  "
                        f"V {reading.voltage_mv:>9.3f} mV  {reading.quality}"
                    )
        finally:
            ser.write(b"x\n")  # never leave the drive energised

    path = Path(args.out)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)
    print(f"\nAppended {len(rows)} rows to {path}")
    print("Change the resistor and run again, then run the fit subcommand.")
    return 0


def fit_command(args: argparse.Namespace) -> int:
    with Path(args.csv).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if args.only_ok:
        rows = [row for row in rows if row["quality"] == "OK"]
    print(format_fit_report(fit_by_dac_code(rows)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("measure", help="sweep DAC codes at one fitted resistor")
    run.add_argument("--port", required=True)
    run.add_argument("--baud", type=int, default=115200)
    run.add_argument("--load-ohms", type=float, required=True)
    run.add_argument("--codes", default="0,100,200,400")
    run.add_argument("--repeat", type=int, default=3)
    run.add_argument("--samples", type=int, default=8)
    run.add_argument("--current-range", default="high", choices=tuple(CURRENT_RANGES))
    run.add_argument("--out", default="phase3a_logs/dummy-load-sweep.csv")
    run.set_defaults(func=measure)

    report = sub.add_parser("fit", help="solve for Rout across the measured loads")
    report.add_argument("csv")
    report.add_argument(
        "--only-ok",
        action="store_true",
        help="drop rows the firmware did not flag OK before fitting",
    )
    report.set_defaults(func=fit_command)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
