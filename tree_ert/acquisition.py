from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import serial

import phase3a_unified_reconstruct as unified
from tree_ert.settings import UiSettings


class Acquisition(Protocol):
    def connect(self, settings: UiSettings) -> None: ...
    def configure(self, settings: UiSettings) -> None: ...
    def capture_frame(self) -> unified.UnifiedFrame: ...
    def send_command(self, command: str) -> list[str]: ...
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
        return [f"[demo] {command.strip()}"]

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
