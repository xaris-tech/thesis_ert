"""Battery state from the Waveshare UPS HAT (E) on the Raspberry Pi (ADR-0084).

The HAT's MCU exposes everything at I2C address 0x2D on bus 1; the register
map is Waveshare's "UPS HAT (E) Register" wiki page and the reads below mirror
its ``ups.py`` demo. All multi-byte values are little-endian 16-bit.

``decode`` is pure so it is testable on any machine. ``read_battery`` returns
``None`` whenever there is no HAT -- Windows, no smbus, no device at 0x2D -- so
the UI simply hides the indicator rather than showing an error.
"""

from __future__ import annotations

from dataclasses import dataclass

I2C_BUS = 1
I2C_ADDRESS = 0x2D
LOW_CELL_MV = 3150
"""Waveshare's own low-cell threshold from ``ups.py``."""

LOW_PERCENT = 20

SHUTDOWN_CURRENT_MA = 50
"""Below this battery current the pack is not being meaningfully charged
(Waveshare ``ups.py``), so a low cell will keep falling."""

SHUTDOWN_GRACE_S = 60
"""How long a cell must stay low before ``ups_shutdown.py`` powers off."""

SHUTDOWN_FLAG = "/run/erterface-ups/shutdown-at"
"""Written by the root service with the planned poweroff time (epoch
seconds) while the countdown runs, so the UI can warn the operator."""


@dataclass(frozen=True)
class BatteryStatus:
    percent: int
    voltage_mv: int
    current_ma: int  # positive charging, negative discharging
    state: str  # "fast charging" | "charging" | "discharging" | "idle"
    minutes_left: int | None  # to empty when discharging, to full when charging
    vbus_mv: int
    cells_mv: tuple[int, ...]

    @property
    def charging(self) -> bool:
        return self.state in ("fast charging", "charging")

    @property
    def low(self) -> bool:
        if self.charging:
            return False
        return self.percent <= LOW_PERCENT or any(
            0 < mv < LOW_CELL_MV for mv in self.cells_mv
        )


def needs_shutdown(status: BatteryStatus) -> bool:
    """A cell is under Waveshare's 3150 mV floor and no charger is saving it."""
    return status.current_ma < SHUTDOWN_CURRENT_MA and any(
        0 < mv < LOW_CELL_MV for mv in status.cells_mv
    )


def planned_shutdown(path: str = SHUTDOWN_FLAG) -> float | None:
    """Epoch seconds of the root service's planned poweroff, or None."""
    try:
        with open(path, encoding="ascii") as handle:
            return float(handle.read().strip())
    except (OSError, ValueError):
        return None


def _u16(data, index: int) -> int:
    return data[index] | data[index + 1] << 8


def decode(status: int, vbus: list[int], battery: list[int], cells: list[int]) -> BatteryStatus:
    """Decode the raw blocks read from 0x02 (1 byte), 0x10 (6), 0x20 (12), 0x30 (8)."""
    if status & 0x40:
        state = "fast charging"
    elif status & 0x80:
        state = "charging"
    elif status & 0x20:
        state = "discharging"
    else:
        state = "idle"
    current = _u16(battery, 2)
    if current > 0x7FFF:
        current -= 0x10000
    if current < 0:
        minutes = _u16(battery, 8)
    elif current > 0:
        minutes = _u16(battery, 10)
    else:
        minutes = None
    return BatteryStatus(
        percent=max(0, min(100, _u16(battery, 4))),
        voltage_mv=_u16(battery, 0),
        current_ma=current,
        state=state,
        minutes_left=minutes,
        vbus_mv=_u16(vbus, 0),
        cells_mv=tuple(_u16(cells, i) for i in range(0, 8, 2)),
    )


def read_battery(bus=None) -> BatteryStatus | None:
    """Read the HAT once, or ``None`` if it is not there."""
    try:
        if bus is None:
            try:
                from smbus2 import SMBus
            except ImportError:
                from smbus import SMBus  # Raspberry Pi OS: python3-smbus
            bus = SMBus(I2C_BUS)
        status = bus.read_i2c_block_data(I2C_ADDRESS, 0x02, 1)[0]
        vbus = bus.read_i2c_block_data(I2C_ADDRESS, 0x10, 6)
        battery = bus.read_i2c_block_data(I2C_ADDRESS, 0x20, 12)
        cells = bus.read_i2c_block_data(I2C_ADDRESS, 0x30, 8)
    except (ImportError, OSError):
        return None
    return decode(status, vbus, battery, cells)


def format_battery(status: BatteryStatus) -> str:
    """Header text beside the painted icon, e.g. ``87%`` or ``62%  3h05m``."""
    text = f"{status.percent}%"
    if status.minutes_left and status.current_ma < 0:
        hours, minutes = divmod(status.minutes_left, 60)
        text += f"  {hours}h{minutes:02d}m"
    return text


def battery_tooltip(status: BatteryStatus) -> str:
    cells = ", ".join(f"{mv / 1000:.2f} V" for mv in status.cells_mv if mv)
    return (
        f"UPS HAT (E): {status.state}\n"
        f"Battery {status.voltage_mv / 1000:.2f} V, {status.current_ma:+d} mA\n"
        f"Cells: {cells or 'n/a'}\n"
        f"USB-C input {status.vbus_mv / 1000:.2f} V"
    )
