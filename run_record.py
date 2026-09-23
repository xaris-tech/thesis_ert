"""Per-run capture records: raw frames plus the physical conditions they were taken under.

The flat ``phase3a_logs/*.csv`` convention records what the *instrument* was doing
(the ``FRAME`` header carries pattern, DAC, settle and sample count) but nothing
about the *specimen*. That was survivable on a trunk, whose state changed only
between sessions. It is not survivable in a saline tank that is titrated during a
session: a dozen captures minutes apart, each at a different concentration, are
indistinguishable afterwards.

A run record is one directory holding everything needed to interpret one capture:

    runs/20260911-203000-titration-step3/
        conditions.json     machine-readable conditions + settings + git commit
        conditions.md       the same, human-readable, for the lab notebook
        frames.csv          every measurement of every frame, unaveraged
        raw/frame-001.txt   verbatim serial text, as received
        media/              photographs, e.g. top-down tank shot as ground truth

Frames are stored unaveraged on purpose. Frame-to-frame spread is the noise
floor, and the noise floor is what licenses any detection claim; averaging at
capture time destroys the measurement that matters most. See ADR-0023.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

RUNS_DIRNAME = "runs"

FRAME_CSV_COLUMNS = [
    "frame_index",
    "frame_id",
    "pattern",
    "dac_code",
    "settle_ms",
    "sample_count",
    "record_index",
    "polarity",
    "i_plus",
    "i_minus",
    "v_plus",
    "v_minus",
    "voltage_mv",
    "current_ua",
    "quality",
]

GROUNDING_FLOATING = "floating"
GROUNDING_GROUNDED = "grounded"
VALID_GROUNDING = (GROUNDING_FLOATING, GROUNDING_GROUNDED, "unknown")


@dataclass
class Conditions:
    """Physical state of the specimen at capture time.

    Every field is optional because a run is worth recording even when a value
    was not measured -- an explicit ``None`` in the record says "not measured",
    which is information. A missing file says nothing at all.
    """

    medium: str = "unknown"
    """Free text: 'saline tank', 'coconut trunk', 'dry bucket', 'dummy load'."""

    saline_g_per_l: float | None = None
    """Cumulative salt added per litre. The titration variable."""

    fill_depth_mm: float | None = None
    """Waterline height above the nail axis. Sets 2-D vs 3-D current spread."""

    water_temp_c: float | None = None
    """Conductivity is strongly temperature dependent; a drift run without this
    number cannot separate thermal drift from instrument drift."""

    electrode_protrusion_mm: float | None = None
    """Bare metal wetted per electrode. PyEIT assumes a boundary point."""

    grounding: str = "unknown"
    """'floating' or 'grounded' -- the CMRR discriminator (ADR-0021)."""

    tank_contents: str = ""
    """What is in the medium besides the medium: 'empty', 'steel rod at E3, r=0.6'."""

    target_description: str = ""
    """What this run is meant to image, if anything. Empty for a baseline."""

    electrode_map: str = ""
    """Which physical nail is E1 and which way numbering runs, e.g.
    'E1 = marked nail, numbering clockwise viewed from above'."""

    specimen_id: str = ""
    """Which physical specimen this is, e.g. 'disc-03', 'coconut-tree-1'.

    Two runs of the same specimen may be differenced; two runs of different
    specimens may not, because a cross-specimen difference images the specimens
    rather than any change in one. The label alone cannot be trusted for this --
    ten discs were all labelled 'reistor-belt-sanity-test' before this field
    existed -- so the identity is recorded explicitly."""

    circumference_mm: float | None = None
    """Circumference at the electrode ring. With the per-nail arc positions in
    ``extra`` it fixes the real electrode geometry."""

    thickness_mm: float | None = None
    """Specimen thickness along the trunk axis. A thin disc approximates the
    two-dimensional domain the solver assumes; a standing trunk does not, and
    this number is how far from that assumption a specimen sits."""

    major_diameter_mm: float | None = None
    """Longest width across the electrode ring."""

    minor_diameter_mm: float | None = None
    """Shortest width across the electrode ring. Recorded with the major so
    ovality is measurable: reconstruction assumes a circular boundary, and
    nothing in the record said how far a specimen departed from one."""

    operator: str = ""
    notes: str = ""

    extra: dict[str, Any] = field(default_factory=dict)
    """Anything this schema did not anticipate. Prefer adding a field over
    burying a recurring value here."""

    def validate(self) -> list[str]:
        """Return human-readable problems. Empty list means usable.

        Deliberately returns warnings rather than raising: a capture already
        taken must always be recordable. Refusing to write the record because
        the temperature was not noted would lose the data as well as the note.
        """
        problems: list[str] = []
        if not self.medium or self.medium == "unknown":
            problems.append("medium is not set")
        if self.grounding not in VALID_GROUNDING:
            problems.append(
                f"grounding {self.grounding!r} is not one of {VALID_GROUNDING}"
            )
        elif self.grounding == "unknown":
            # Grounding is the discriminator for the CMRR hypothesis behind the
            # 57.5% reciprocity violation (ADR-0021). A run whose grounding
            # state was not noted cannot contribute to that comparison at all,
            # so an unrecorded value is reported rather than quietly accepted.
            problems.append("grounding is not recorded (floating or grounded?)")
        if self.saline_g_per_l is not None and self.saline_g_per_l < 0:
            problems.append("saline_g_per_l is negative")
        if self.fill_depth_mm is not None and self.fill_depth_mm < 0:
            problems.append("fill_depth_mm is negative")
        if self.electrode_protrusion_mm is not None and self.electrode_protrusion_mm < 0:
            problems.append("electrode_protrusion_mm is negative")
        for name in (
            "circumference_mm",
            "thickness_mm",
            "major_diameter_mm",
            "minor_diameter_mm",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                problems.append(f"{name} is negative")
        major, minor = self.major_diameter_mm, self.minor_diameter_mm
        if major is not None and minor is not None and minor > major:
            problems.append("minor_diameter_mm is larger than major_diameter_mm")
        return problems


def git_commit(repo_root: Path | None = None) -> str | None:
    """Short commit hash of the working tree, or None outside a repo.

    Recorded so a run can be replayed against the code that produced it. A
    dirty tree is marked, because a run taken against uncommitted edits is not
    reproducible from the hash alone.
    """
    root = repo_root or Path(__file__).resolve().parent
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if head.returncode != 0:
            return None
        commit = head.stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if dirty.returncode == 0 and dirty.stdout.strip():
            commit += "-dirty"
        return commit
    except (OSError, subprocess.SubprocessError):
        return None


def slugify(label: str) -> str:
    """Filesystem-safe run label. Empty input yields 'run'."""
    cleaned = [c.lower() if c.isalnum() else "-" for c in label.strip()]
    slug = "".join(cleaned).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:60] or "run"


def run_dirname(label: str, when: datetime | None = None) -> str:
    stamp = (when or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{slugify(label)}"


def _record_row(
    frame: Any, frame_index: int, record_index: int, record: Any
) -> list[str]:
    return [
        str(frame_index),
        str(frame.frame_id),
        frame.pattern,
        str(frame.dac_code),
        str(frame.settle_ms),
        str(frame.sample_count),
        str(record_index),
        record.polarity,
        f"E{record.i_pair[0] + 1}",
        f"E{record.i_pair[1] + 1}",
        f"E{record.v_pair[0] + 1}",
        f"E{record.v_pair[1] + 1}",
        f"{record.voltage_mv:.6f}",
        f"{record.current_ua:.6f}",
        record.quality,
    ]


def conditions_markdown(
    conditions: Conditions,
    settings: dict[str, Any],
    metadata: dict[str, Any],
) -> str:
    """Lab-notebook rendering of one run's context.

    Exists alongside conditions.json because the JSON is for tooling and this
    is for a person -- including a thesis panel asking where a number came
    from, who should not have to read JSON to find out.
    """
    lines = [f"# Run {metadata.get('run_id', '?')}", ""]
    lines.append(f"- **Captured:** {metadata.get('created_at', '?')}")
    if metadata.get("git_commit"):
        lines.append(f"- **Code version:** `{metadata['git_commit']}`")
    if metadata.get("label"):
        lines.append(f"- **Label:** {metadata['label']}")
    lines.append("")

    lines.append("## Conditions")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    for key, value in asdict(conditions).items():
        if key == "extra":
            continue
        shown = "_not recorded_" if value in (None, "") else value
        lines.append(f"| {key} | {shown} |")
    for key, value in conditions.extra.items():
        lines.append(f"| {key} (extra) | {value} |")
    lines.append("")

    if settings:
        lines.append("## Instrument settings")
        lines.append("")
        lines.append("| Setting | Value |")
        lines.append("|---|---|")
        for key, value in settings.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")

    problems = conditions.validate()
    if problems:
        lines.append("## Incomplete")
        lines.append("")
        lines.append(
            "These were not recorded at capture time and cannot be recovered later:"
        )
        lines.append("")
        for problem in problems:
            lines.append(f"- {problem}")
        lines.append("")

    if conditions.notes:
        lines.append("## Notes")
        lines.append("")
        lines.append(conditions.notes)
        lines.append("")

    return "\n".join(lines)


class RunRecorder:
    """One capture run on disk.

    Opened before the first frame and closed after the last, so a session that
    crashes mid-capture still leaves every frame it managed to read. Frames are
    appended and flushed one at a time rather than buffered to the end.
    """

    def __init__(
        self,
        root: Path,
        label: str,
        conditions: Conditions | None = None,
        settings: dict[str, Any] | None = None,
        when: datetime | None = None,
    ) -> None:
        created = when or datetime.now()
        self.label = label
        self.run_id = run_dirname(label, created)
        self.path = Path(root) / self.run_id
        self.raw_dir = self.path / "raw"
        self.media_dir = self.path / "media"
        self.path.mkdir(parents=True, exist_ok=True)

        self.conditions = conditions or Conditions()
        self.settings = dict(settings or {})
        self.metadata = {
            "run_id": self.run_id,
            "label": label,
            "created_at": created.isoformat(timespec="seconds"),
            "git_commit": git_commit(),
        }

        self.frames_written = 0
        self._frames_path = self.path / "frames.csv"
        self._handle = self._frames_path.open("w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._handle)
        self._writer.writerow(FRAME_CSV_COLUMNS)
        self._handle.flush()
        self.write_conditions()

    # -- context manager -------------------------------------------------

    def __enter__(self) -> "RunRecorder":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- writing ---------------------------------------------------------

    def write_conditions(self) -> None:
        """(Re)write conditions.json and conditions.md.

        Called on open so a crashed run is still interpretable, and callable
        again after late edits -- the operator often measures the water
        temperature while the scan is already running.
        """
        payload = {
            **self.metadata,
            "conditions": asdict(self.conditions),
            "settings": self.settings,
            "incomplete": self.conditions.validate(),
        }
        (self.path / "conditions.json").write_text(
            json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8"
        )
        (self.path / "conditions.md").write_text(
            conditions_markdown(self.conditions, self.settings, self.metadata),
            encoding="utf-8",
        )

    def update_conditions(self, conditions: Conditions) -> None:
        self.conditions = conditions
        self.write_conditions()

    def write_frame(self, frame: Any, raw_lines: Sequence[str] | None = None) -> int:
        """Append one frame's records. Returns its zero-based frame index.

        ``frame`` is any object shaped like ``UnifiedFrame``; the module is kept
        free of a ``phase3a_unified_reconstruct`` import so the Qt UI and the
        CLI can both depend on it without a cycle.
        """
        index = self.frames_written
        for record_index, record in enumerate(frame.records):
            self._writer.writerow(_record_row(frame, index, record_index, record))
        self._handle.flush()
        if raw_lines is not None:
            self.write_raw(index, raw_lines)
        self.frames_written += 1
        return index

    def write_raw(self, frame_index: int, lines: Iterable[str]) -> Path:
        """Store the verbatim serial text for one frame.

        The parsed CSV is a lossy view: a malformed record that the parser
        rejected leaves no trace in it. The raw text is the only artifact that
        can settle a later argument about whether the instrument or the parser
        was at fault.
        """
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path = self.raw_dir / f"frame-{frame_index + 1:03d}.txt"
        text = "\n".join(str(line).rstrip("\r\n") for line in lines)
        path.write_text(text + "\n", encoding="utf-8")
        return path

    def attach(self, source: Path, name: str | None = None) -> Path:
        """Copy a photograph or other artifact into the run's media directory.

        The top-down tank photograph is ground truth for a target run: without
        it, a localisation error is an assertion rather than a measurement.
        """
        source = Path(source)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        destination = self.media_dir / (name or source.name)
        shutil.copy2(source, destination)
        return destination

    def write_text(self, name: str, text: str) -> Path:
        """Drop an arbitrary report (reciprocity CSV, drift summary) into the run."""
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def index_row(self, **metrics: Any) -> dict[str, Any]:
        """This run's row for the scans index, with metrics merged in.

        Built here rather than in the caller so the conditions and settings in
        the index cannot drift from the ones in ``conditions.json`` -- they come
        from the same objects.
        """
        row: dict[str, Any] = {
            "run_id": self.run_id,
            "captured_at": self.metadata.get("created_at"),
            "label": self.label,
            "medium": self.conditions.medium,
            "saline_g_per_l": self.conditions.saline_g_per_l,
            "fill_depth_mm": self.conditions.fill_depth_mm,
            "water_temp_c": self.conditions.water_temp_c,
            "electrode_protrusion_mm": self.conditions.electrode_protrusion_mm,
            "grounding": self.conditions.grounding,
            "tank_contents": self.conditions.tank_contents,
            "target": self.conditions.target_description,
            "specimen_id": self.conditions.specimen_id,
            "circumference_mm": self.conditions.circumference_mm,
            "thickness_mm": self.conditions.thickness_mm,
            "major_diameter_mm": self.conditions.major_diameter_mm,
            "minor_diameter_mm": self.conditions.minor_diameter_mm,
            "pattern": self.settings.get("pattern"),
            "current_range": self.settings.get("current_range"),
            "dac": self.settings.get("dac"),
            "settle_ms": self.settings.get("settle_ms"),
            "samples": self.settings.get("samples"),
            "frames": self.frames_written,
            "git_commit": self.metadata.get("git_commit"),
            "path": self.run_id,
        }
        row.update(metrics)
        return row

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()


def create_run(
    log_dir: Path,
    label: str,
    conditions: Conditions | None = None,
    settings: dict[str, Any] | None = None,
    when: datetime | None = None,
) -> RunRecorder:
    """Open a run under ``<log_dir>/runs/``."""
    return RunRecorder(Path(log_dir) / RUNS_DIRNAME, label, conditions, settings, when)


def load_run(path: Path) -> dict[str, Any]:
    """Read back a run's conditions.json. Raises if the run is not a run."""
    payload = json.loads((Path(path) / "conditions.json").read_text(encoding="utf-8"))
    payload["conditions"] = Conditions(**payload.get("conditions", {}))
    return payload


def list_runs(log_dir: Path) -> list[Path]:
    """Run directories under ``<log_dir>/runs/``, newest last."""
    runs_dir = Path(log_dir) / RUNS_DIRNAME
    if not runs_dir.is_dir():
        return []
    return sorted(p for p in runs_dir.iterdir() if (p / "conditions.json").is_file())


# -- session log ---------------------------------------------------------


class SessionLog:
    """Append-only log of everything the UI printed, across every run.

    The window's log pane is in-memory: close the app and the record of what
    warmed up, what was flagged, and what the operator was told is gone. That is
    the half of a session that never reaches ``frames.csv`` -- a warmup frame
    that read badly before the recorded run started, a cancelled attempt, a
    failure and its retry -- and it is exactly what a later reader needs to know
    why a run looks the way it does.

    One file per scans root, not per run, because the interesting sequence is
    usually *between* runs during a titration.
    """

    FILENAME = "session.log"

    def __init__(self, root: Path) -> None:
        self.path = Path(root) / self.FILENAME
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")

    def write(self, message: str, when: datetime | None = None) -> None:
        stamp = (when or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
        self._handle.write(f"{stamp}  {message}\n")
        self._handle.flush()

    def banner(self, message: str, when: datetime | None = None) -> None:
        """A visually separated entry, for session starts and run boundaries."""
        self._handle.write("\n" + "-" * 72 + "\n")
        self.write(message, when)

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()

    def __enter__(self) -> "SessionLog":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


# -- scan index ----------------------------------------------------------

INDEX_FILENAME = "index.csv"

INDEX_COLUMNS = [
    "run_id",
    "captured_at",
    "label",
    "medium",
    "saline_g_per_l",
    "fill_depth_mm",
    "water_temp_c",
    "electrode_protrusion_mm",
    "grounding",
    "tank_contents",
    "target",
    "pattern",
    "current_range",
    "dac",
    "settle_ms",
    "samples",
    "frames",
    "reciprocity_median_percent",
    "reciprocity_max_percent",
    "reciprocity_sign_flips",
    "reciprocity_pairs",
    "noise_median_kohm",
    "noise_median_percent",
    "outcome",
    "baseline_run",
    "peak_value",
    "peak_angle_deg",
    "control_peak",
    "significance",
    "git_commit",
    "path",
    "reciprocity_gate",
    "specimen_id",
    "circumference_mm",
    "thickness_mm",
    "major_diameter_mm",
    "minor_diameter_mm",
]


def _index_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def append_index_row(root: Path, row: dict[str, Any]) -> Path:
    """Append one scan to ``<root>/index.csv``, writing the header if new.

    The index is a convenience, not the record: every value in it also lives in
    the run's own ``conditions.json``. It exists because a titration series is
    read as a table -- resistance against concentration, reciprocity against
    grounding -- and opening twenty directories to build that table by hand is
    how a series stops being analysed.

    Unknown keys are ignored and missing ones written empty, so adding a column
    later cannot break reading a file written before it existed.
    """
    path = Path(root) / INDEX_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(INDEX_COLUMNS)
        writer.writerow([_index_value(row.get(column)) for column in INDEX_COLUMNS])
    return path


def read_index(root: Path) -> list[dict[str, str]]:
    """Every scan recorded in ``<root>/index.csv``, oldest first."""
    path = Path(root) / INDEX_FILENAME
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
