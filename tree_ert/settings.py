from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from pathlib import Path


VALID_PATTERNS = ("adjacent", "opposite", "skip-1", "skip-2")
# Current-range jumper. Rs is physical and the firmware cannot read it back, so
# the UI has to declare it every session or the firmware keeps its RANGE_LOW
# default and guards against LOW's 100 uA ceiling (ADR-0011). On a rig whose
# fitted Rs is 10 ohm that flags every legitimate measurement as I_HIGH.
# Values are (firmware command, Rs ohms, DAC ceiling) from
# docs/first-working-prototype/03-howland-current-source.md.
CURRENT_RANGES = {
    "low": ("el", 68.0, 420),
    "medium": ("em", 22.0, 680),
    "high": ("eh", 10.0, 620),
}
VALID_CURRENT_RANGES = tuple(CURRENT_RANGES)
SETTINGS_FILENAME = "ui_settings.json"


def parse_int_field(name: str, value: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def parse_float_field(name: str, value: str, minimum: float | None = None) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{name} must be at least {minimum:g}")
    return parsed


@dataclass(frozen=True)
class UiSettings:
    port: str = "COM3"
    baud: int = 115200
    pattern: str = "adjacent"
    # Must match the Rs jumper actually fitted. Defaults to "high" because the
    # only Rs on this board is 10 ohm - LOW and MEDIUM cannot be selected in
    # hardware at all. Declaring it is what sets STATUS RS_DECLARED to 1.
    current_range: str = "high"
    dac: int = 100
    settle_ms: int = 30
    samples: int = 4
    warmup_frames: int = 10
    # Frames discarded at the start of a target run. Inserting the target leaves
    # the hardware idle, and re-energising restarts the electrode double layer
    # from cold; those first frames drift regardless of what the target is.
    target_warmup_frames: int = 5
    baseline_frames: int = 10
    frames: int = 20
    diameter_cm: float | None = None
    log_dir: Path = Path("phase3a_logs")
    log_enabled: bool = True
    allow_unstable_baseline: bool = False
    # Drop individual bad measurements instead of failing the whole capture.
    # Separate from allow_unstable_baseline: that rescues the stability gate,
    # this rescues a single I_LOW record that would otherwise abort the run.
    lenient_quality: bool = False
    # Substitute unstable pairs with their baseline value before reconstructing.
    # Turn off to see the raw difference: the filter asserts "nothing changed"
    # for every pair it drops, which can erase a genuine target whose change
    # exceeds MAX_RECON_PAIR_DELTA_KOHM.
    filter_pairs: bool = True
    # Physical-to-mesh electrode mapping. The firmware reports the electrode
    # labels as wired; PyEIT's mesh has its own index order. If the ring was
    # installed running the opposite way round, or starting at a different
    # electrode, every reconstruction is mirrored or rotated by a fixed amount.
    # Defaults are identity - change only from a ground-truth run with a target
    # at a known electrode.
    electrode_offset: int = 0
    electrode_reversed: bool = False
    # Frames the self test captures to judge repeatability. Two is the minimum
    # that can disagree; more is slower but screens a rig that only drifts after
    # the first few frames.
    self_test_frames: int = 3
    # Resistance of the current-sense shunt physically fitted to the board. The
    # self test compares it against what the firmware reports: a mismatch scales
    # every measured current, and therefore every transfer resistance, by a
    # constant the data itself gives no sign of. None means "not measured yet".
    expected_shunt_ohms: float | None = None

    @classmethod
    def default(cls) -> "UiSettings":
        return cls()

    def range_command(self) -> bytes:
        """Firmware command that declares the fitted Rs jumper."""
        return (CURRENT_RANGES[self.current_range][0] + "\n").encode()

    def range_rs_ohms(self) -> float:
        return CURRENT_RANGES[self.current_range][1]

    def max_dac_code(self) -> int:
        return CURRENT_RANGES[self.current_range][2]

    def validate(self) -> "UiSettings":
        if not self.port.strip():
            raise ValueError("port is required")
        if self.baud <= 0:
            raise ValueError("baud must be positive")
        if self.pattern not in VALID_PATTERNS:
            raise ValueError(f"pattern must be one of {', '.join(VALID_PATTERNS)}")
        if self.current_range not in CURRENT_RANGES:
            raise ValueError(
                f"current_range must be one of {', '.join(VALID_CURRENT_RANGES)}"
            )
        ceiling = self.max_dac_code()
        if self.dac < 0 or self.dac > ceiling:
            raise ValueError(
                f"dac must be between 0 and {ceiling} on the "
                f"{self.current_range} current range"
            )
        if self.settle_ms <= 0:
            raise ValueError("settle_ms must be positive")
        if self.samples <= 0:
            raise ValueError("samples must be positive")
        if self.warmup_frames < 0:
            raise ValueError("warmup_frames cannot be negative")
        if self.target_warmup_frames < 0:
            raise ValueError("target_warmup_frames cannot be negative")
        if self.baseline_frames <= 0:
            raise ValueError("baseline_frames must be positive")
        if self.frames <= 0:
            raise ValueError("frames must be positive")
        if self.diameter_cm is not None and self.diameter_cm <= 0:
            raise ValueError("diameter_cm must be positive")
        if not 0 <= self.electrode_offset < 12:
            raise ValueError("electrode_offset must be between 0 and 11")
        if self.self_test_frames < 2:
            raise ValueError("self_test_frames must be at least 2")
        if self.expected_shunt_ohms is not None and self.expected_shunt_ohms <= 0:
            raise ValueError("expected_shunt_ohms must be positive")
        return self


def settings_to_dict(settings: UiSettings) -> dict:
    data = {}
    for field in fields(settings):
        value = getattr(settings, field.name)
        data[field.name] = str(value) if isinstance(value, Path) else value
    return data


def settings_from_dict(data: dict, default: UiSettings | None = None) -> UiSettings:
    """Rebuild settings, ignoring unknown or unusable keys.

    A settings file written by an older build must not stop the UI starting, so
    anything that does not fit falls back to the default value.
    """
    base = default or UiSettings.default()
    known = {field.name for field in fields(base)}
    updates: dict = {}
    for name, value in data.items():
        if name not in known:
            continue
        if name == "log_dir":
            updates[name] = Path(value)
        else:
            updates[name] = value
    try:
        return replace(base, **updates).validate()
    except (TypeError, ValueError):
        return base


def settings_path(log_dir: Path) -> Path:
    return Path(log_dir) / SETTINGS_FILENAME


def save_settings(settings: UiSettings, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings_to_dict(settings), indent=2), encoding="utf-8")


def load_settings(path: Path, default: UiSettings | None = None) -> UiSettings | None:
    """Return stored settings, or None when there is nothing usable to restore."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return settings_from_dict(data, default)
