from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VALID_PATTERNS = ("adjacent", "opposite", "skip-1", "skip-2")


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
    dac: int = 100
    settle_ms: int = 30
    samples: int = 4
    warmup_frames: int = 10
    baseline_frames: int = 10
    frames: int = 20
    diameter_cm: float | None = None
    log_dir: Path = Path("phase3a_logs")
    log_enabled: bool = True
    allow_unstable_baseline: bool = False

    @classmethod
    def default(cls) -> "UiSettings":
        return cls()

    def validate(self) -> "UiSettings":
        if not self.port.strip():
            raise ValueError("port is required")
        if self.baud <= 0:
            raise ValueError("baud must be positive")
        if self.pattern not in VALID_PATTERNS:
            raise ValueError(f"pattern must be one of {', '.join(VALID_PATTERNS)}")
        if self.dac < 0 or self.dac > 620:
            raise ValueError("dac must be between 0 and 620")
        if self.settle_ms <= 0:
            raise ValueError("settle_ms must be positive")
        if self.samples <= 0:
            raise ValueError("samples must be positive")
        if self.warmup_frames < 0:
            raise ValueError("warmup_frames cannot be negative")
        if self.baseline_frames <= 0:
            raise ValueError("baseline_frames must be positive")
        if self.frames <= 0:
            raise ValueError("frames must be positive")
        if self.diameter_cm is not None and self.diameter_cm <= 0:
            raise ValueError("diameter_cm must be positive")
        return self
