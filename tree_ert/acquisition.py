from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import serial

import phase3a_unified_reconstruct as unified
from tree_ert.settings import UiSettings


@dataclass(frozen=True)
class DacAddressResult:
    """Outcome of binding the firmware's DAC driver to a scanned address."""

    address: int | None
    detail: str

    @property
    def resolved(self) -> bool:
        return self.address is not None


class Acquisition(Protocol):
    def connect(self, settings: UiSettings) -> None: ...
    def configure(self, settings: UiSettings) -> None: ...
    def capture_frame(self) -> unified.UnifiedFrame: ...
    def send_command(self, command: str) -> list[str]: ...
    def select_dac_address(self) -> DacAddressResult: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...


@dataclass
class DemoAcquisition:
    stopped: bool = False
    frame_id: int = 0
    pattern: str = "adjacent"
    dac_code: int = 100
    settle_ms: int = 30
    sample_count: int = 4
    dac_address: int = 0x61

    def connect(self, settings: UiSettings) -> None:
        self.configure(settings)
        self.stopped = False

    def configure(self, settings: UiSettings) -> None:
        self.pattern = settings.pattern
        self.dac_code = settings.dac
        self.settle_ms = settings.settle_ms
        self.sample_count = settings.samples

    def capture_frame(self) -> unified.UnifiedFrame:
        self.frame_id += 1
        protocol, _ = unified.protocol_and_command(self.pattern)
        records = []
        rng = np.random.default_rng(self.frame_id)
        for ex_index, ex_pair in enumerate(protocol.ex_mat):
            i_plus = int(ex_pair[0])
            i_minus = int(ex_pair[1])
            for meas_pair in protocol.meas_mat[ex_index]:
                v_plus = int(meas_pair[1])
                v_minus = int(meas_pair[0])
                base_mv = 20.0 * np.sin((i_plus + v_plus + 1) / 3.0)
                noise = float(rng.normal(0.0, 0.05))
                records.append(unified.MeasurementRecord(
                    polarity="FWD",
                    i_pair=(i_plus, i_minus),
                    v_pair=(v_plus, v_minus),
                    voltage_mv=base_mv + noise,
                    current_ua=250.0,
                    quality="OK",
                ))
                records.append(unified.MeasurementRecord(
                    polarity="REV",
                    i_pair=(i_minus, i_plus),
                    v_pair=(v_plus, v_minus),
                    voltage_mv=-(base_mv + noise),
                    current_ua=250.0,
                    quality="OK",
                ))
        return unified.UnifiedFrame(
            frame_id=self.frame_id,
            pattern=self.pattern,
            dac_code=self.dac_code,
            settle_ms=self.settle_ms,
            sample_count=self.sample_count,
            records=records,
        )

    def send_command(self, command: str) -> list[str]:
        """Answer the commands the self test depends on, ignore the rest.

        Demo mode exists so the host path can be exercised with no board, and a
        self test that skipped every hardware check in demo mode would never
        exercise the parsing those checks are built on.
        """
        text = command.strip()
        if text == "?":
            return [self._demo_status_line()]
        if text == "i":
            return [
                "I2C_SCAN,BEGIN",
                "I2C_DEVICE,0x48",
                f"I2C_DEVICE,0x{self.dac_address:02X}",
                "I2C_SCAN,END,FOUND,2",
            ]
        return [f"[demo] {text}"]

    def _demo_status_line(self) -> str:
        return (
            "STATUS,2,MODE," + self.pattern.upper()
            + f",DAC,{self.dac_code}"
            + f",SETTLE,{self.settle_ms}"
            + ",DISCHARGE,0"
            + f",SAMPLES,{self.sample_count}"
            + ",RANGE,LOW,RS_OHMS,68.0,MAX_DAC_CODE,420,SHUNT_OHMS,97.90"
            + f",DAC_ADDR,0x{self.dac_address:02X}"
            + ",VGAIN_AUTO,1,VRANGE_MV,256.0,MIN_CURRENT_UA,1.0,MAX_CURRENT_UA,1200.0"
        )

    def select_dac_address(self) -> DacAddressResult:
        return DacAddressResult(self.dac_address, f"demo DAC at 0x{self.dac_address:02x}")

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.stop()


class SerialAcquisition:
    def __init__(self) -> None:
        self._serial: serial.Serial | None = None

    def connect(self, settings: UiSettings) -> None:
        self._serial = serial.Serial(settings.port, settings.baud, timeout=1.0)
        self._serial.reset_input_buffer()

    def configure(self, settings: UiSettings) -> None:
        if self._serial is None:
            raise RuntimeError("serial connection is not open")
        _, mode_command = unified.protocol_and_command(settings.pattern)
        self._serial.write(mode_command)
        self._serial.write(f"p{settings.dac}\n".encode())
        self._serial.write(f"t{settings.settle_ms}\n".encode())
        self._serial.write(f"n{settings.samples}\n".encode())

    def capture_frame(self) -> unified.UnifiedFrame:
        if self._serial is None:
            raise RuntimeError("serial connection is not open")
        return unified.request_frame(self._serial)

    def send_command(self, command: str, reply_timeout: float = 0.6) -> list[str]:
        """Send one firmware command and collect whatever it prints back.

        Lets the UI drive the firmware directly, so the Arduino Serial Monitor
        does not have to be opened - it holds the port exclusively and would
        block the UI from connecting.
        """
        if self._serial is None:
            raise RuntimeError("serial connection is not open")
        self._serial.write(f"{command.strip()}\n".encode())
        deadline = time.monotonic() + reply_timeout
        lines: list[str] = []
        while time.monotonic() < deadline:
            raw = self._serial.readline()
            if not raw:
                if lines:
                    break
                continue
            text = raw.decode(errors="ignore").strip()
            if text:
                lines.append(text)
        return lines

    def select_dac_address(self) -> DacAddressResult:
        """Scan the I2C bus and bind the firmware's DAC driver to what it finds.

        The MCP4725's A0 strap picks the low address bit, and this prototype has
        scanned at both 0x60 and 0x61, so the address is discovered instead of
        assumed. Never raises: a board that cannot be scanned, or an older flash
        without the `b` command, still connects and runs on whatever address the
        firmware chose at boot - it just does not get corrected from here.
        """
        if self._serial is None:
            raise RuntimeError("serial connection is not open")
        scan = self.send_command("i", reply_timeout=2.0)
        addresses = unified.parse_i2c_scan(scan)
        if not addresses:
            return DacAddressResult(None, "no I2C scan reply; left as the firmware set it")
        address = unified.select_dac_address(addresses)
        if address is None:
            listed = ", ".join(f"0x{value:02x}" for value in addresses) or "none"
            return DacAddressResult(
                None,
                f"no single MCP4725 address on the bus (saw {listed}); "
                "left as the firmware set it",
            )
        reply = self.send_command(unified.dac_address_command(address).decode().strip())
        if any("unknown command" in line for line in reply):
            return DacAddressResult(
                None,
                f"found 0x{address:02x} but this firmware has no 'b' command; reflash to set it",
            )
        if any(line.startswith("[ERROR]") for line in reply):
            detail = next(line for line in reply if line.startswith("[ERROR]"))
            return DacAddressResult(None, f"firmware refused 0x{address:02x}: {detail}")
        return DacAddressResult(address, f"DAC bound to 0x{address:02x}")

    def stop(self) -> None:
        if self._serial is not None:
            self._serial.write(b"x\n")

    def close(self) -> None:
        if self._serial is not None:
            try:
                self.stop()
            finally:
                self._serial.close()
                self._serial = None
