#!/usr/bin/env python3
"""Clean poweroff on a flat UPS HAT (E) pack (ADR-0085). Runs as root via
``erterface-ups.service``; install with ``sudo pi/install_ups_service.sh``.

Every 2 s it reads the HAT. When any cell stays under 3150 mV with no charger
current for 60 s (``battery.needs_shutdown``), it tells the HAT to power the Pi
back on when USB-C power returns (register 0x01 <- 0x55, as Waveshare's demo
does) and runs ``systemctl poweroff``. The countdown is published at
``battery.SHUTDOWN_FLAG`` so the farm UI can warn the operator; recovering
(charger plugged in) cancels it. A failed I2C read never triggers a shutdown.
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from erterface import battery  # noqa: E402  (pure module, no Qt)

POLL_S = 2


def _write_flag(deadline):
    os.makedirs(os.path.dirname(battery.SHUTDOWN_FLAG), mode=0o755, exist_ok=True)
    tmp = battery.SHUTDOWN_FLAG + ".tmp"
    with open(tmp, "w", encoding="ascii") as handle:
        handle.write(f"{deadline:.0f}\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, battery.SHUTDOWN_FLAG)


def _clear_flag():
    try:
        os.remove(battery.SHUTDOWN_FLAG)
    except FileNotFoundError:
        pass


def main():
    try:
        from smbus2 import SMBus
    except ImportError:
        from smbus import SMBus
    bus = SMBus(battery.I2C_BUS)
    deadline = None
    _clear_flag()
    while True:
        status = battery.read_battery(bus)
        if status is not None and battery.needs_shutdown(status):
            if deadline is None:
                deadline = time.time() + battery.SHUTDOWN_GRACE_S
                _write_flag(deadline)
                print(f"Cell low ({min(status.cells_mv)} mV); poweroff in "
                      f"{battery.SHUTDOWN_GRACE_S} s unless charged.", flush=True)
            elif time.time() >= deadline:
                print("Battery flat: powering off.", flush=True)
                try:
                    bus.write_byte_data(battery.I2C_ADDRESS, 0x01, 0x55)
                except OSError as exc:
                    print(f"Could not arm power-on-with-charger: {exc}", flush=True)
                subprocess.run(["systemctl", "poweroff"], check=False)
                return 0
        elif status is not None and deadline is not None:
            print("Battery recovered; shutdown cancelled.", flush=True)
            deadline = None
            _clear_flag()
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
