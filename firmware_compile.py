"""Compile the active firmware sketch, to catch what text assertions cannot.

ADR-0005 decided the firmware tests stay text assertions because "there is no
toolchain that could" compile the sketch. That premise no longer holds: the
Arduino IDE ships `arduino-cli`, and the esp32 core needed for this board is
installed. ADR-0016 adds a compile check on top of the text assertions.

This does not verify behaviour, and is not intended to - ADR-0005's reasoning
about simulators and hardware-in-loop is unchanged, and behavioural evidence
still comes from bench sessions. It catches the narrower class the text tests
are blind to: a sketch that does not build. That matters here because the only
way to exercise firmware is to physically flash a board attached to a tree, so a
compile error costs a trip to the rig rather than a test run.

Everything degrades to a skip when the toolchain is absent, so the suite still
runs on a machine with no Arduino install.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ACTIVE_SKETCH = (
    REPO_ROOT
    / "firmware"
    / "esp32s3-phase3a-unified-arduino"
    / "esp32s3_phase3a_unified"
)
# The prototype is a bare ESP32-S3 dev module; see docs/first-working-prototype/.
DEFAULT_FQBN = "esp32:esp32:esp32s3"
# Keeping the build directory stable is what makes the check cheap: a cold build
# is roughly 90 seconds, an unchanged rebuild about 6.
BUILD_CACHE = REPO_ROOT / ".firmware-build"

# Bundled with the Arduino IDE. Checked in order; ARDUINO_CLI overrides all.
CANDIDATE_CLI_PATHS = (
    Path(r"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"),
    Path(r"C:\Program Files (x86)\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"),
    Path.home() / "AppData/Local/Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe",
    Path("/usr/local/bin/arduino-cli"),
    Path("/opt/homebrew/bin/arduino-cli"),
)


@dataclass(frozen=True)
class CompileResult:
    """Outcome of one compile. `output` is stdout and stderr together."""

    ok: bool
    output: str
    flash_bytes: int | None = None
    ram_bytes: int | None = None


def find_arduino_cli() -> Path | None:
    """Locate arduino-cli, or None when nothing usable is installed.

    Returning None rather than raising is deliberate: the caller turns it into a
    skip, so this repo still tests clean on a machine with no Arduino toolchain.
    """
    override = os.environ.get("ARDUINO_CLI")
    if override:
        path = Path(override)
        return path if path.exists() else None
    found = shutil.which("arduino-cli")
    if found:
        return Path(found)
    for candidate in CANDIDATE_CLI_PATHS:
        if candidate.exists():
            return candidate
    return None


def parse_sizes(output: str) -> tuple[int | None, int | None]:
    """Pull flash and RAM totals out of arduino-cli's summary lines.

    Best effort by design - a size line that changes format must not fail a
    compile that actually succeeded, so both values come back None instead.
    """
    flash = ram = None
    for line in output.splitlines():
        text = line.strip()
        if text.startswith("Sketch uses "):
            flash = _first_int(text)
        elif text.startswith("Global variables use "):
            ram = _first_int(text)
    return flash, ram


def _first_int(text: str) -> int | None:
    for token in text.replace(",", "").split():
        if token.isdigit():
            return int(token)
    return None


def compile_sketch(
    sketch: Path = ACTIVE_SKETCH,
    fqbn: str = DEFAULT_FQBN,
    cli: Path | None = None,
    use_cache: bool = True,
) -> CompileResult:
    """Compile one sketch and report whether it built."""
    executable = cli or find_arduino_cli()
    if executable is None:
        raise FileNotFoundError("arduino-cli not found; set ARDUINO_CLI to its path")
    command = [str(executable), "compile", "--fqbn", fqbn, str(sketch)]
    if use_cache:
        command += ["--build-path", str(BUILD_CACHE)]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    flash, ram = parse_sizes(output)
    return CompileResult(
        ok=completed.returncode == 0,
        output=output,
        flash_bytes=flash,
        ram_bytes=ram,
    )


def main() -> int:
    executable = find_arduino_cli()
    if executable is None:
        print("arduino-cli not found; set ARDUINO_CLI to its path")
        return 2
    print(f"arduino-cli: {executable}")
    print(f"sketch:      {ACTIVE_SKETCH}")
    result = compile_sketch(cli=executable)
    print(result.output.strip())
    if result.ok and result.flash_bytes is not None:
        print(f"\nOK - flash {result.flash_bytes} bytes, RAM {result.ram_bytes} bytes")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
