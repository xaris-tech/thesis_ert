# ADR-0084: Read the UPS HAT (E) battery over I2C and sync to Drive in the background

- **Status:** Accepted
- **Date:** 2026-11-06
- **Affects:** `erterface-interface/src/erterface/battery.py`, `erterface-interface/src/erterface/app.py`, `erterface-interface/src/erterface/drive_sync.py`
- **Related:** ADR-0072 (farm UI embeds the capture session)

## Context

The field unit is a Raspberry Pi 5 on a Waveshare UPS HAT (E) (4x 18650). The farm UI
(`erterface-interface`) gave no warning before the pack ran flat mid-scan. Google Drive
upload already existed (`drive_sync.py`, OAuth), but only on a manual **Sync** tap, and it ran
on the GUI thread, so the touch screen froze for the whole upload. At a plantation the Pi is
offline most of the time and online only near the farmhouse Wi-Fi or a phone hotspot.

Waveshare's register manual puts the HAT's MCU at I2C 0x2D on bus 1: status byte 0x02
(bit 6 fast charging, bit 7 charging, bit 5 discharging), VBUS block 0x10 (mV, mA, mW), battery
block 0x20 (mV, signed mA, %, mAh, minutes to empty, minutes to full), cell voltages 0x30.
All values are little-endian 16-bit. Their `ups.py` demo uses a 3150 mV low-cell threshold.

## Decision

Poll the HAT every 10 s and show a painted battery icon, percentage and time to empty in the
top bar, hidden when there is no HAT. Upload pending measurements on a background thread after
each saved scan and every 5 minutes, but only when Google's API host is reachable and only
where no prompt can appear (a stored OAuth token, or `local` mode).

## Rationale

- **The UI reads I2C directly, not a separate daemon.** One process, no IPC, and the read is
  under a millisecond. A systemd battery service would be needed for unattended low-battery
  shutdown, which this does not attempt (see Consequences).
- **The icon is painted, not an emoji.** Raspberry Pi OS fonts lack U+1F50B/U+1FAAB.
- **Signed current uses `- 0x10000`.** Waveshare's demo subtracts `0xFFFF`, which is off by one.
- **Auto-sync reuses `sync_unsynced`** and the per-measurement `synced` flag rather than adding a
  second path such as rclone mirroring of `scans/`. The farm database is what the operator
  works from, and Drive already holds its folder layout.
- **No background OAuth.** A missing or revoked token would open a browser on a headless field
  unit. Background sync skips; the manual Sync button still runs the setup flow.
- **Reachability check first**, so an offline Pi does not record one failure per measurement.

## Consequences

- The Pi does not shut itself down on a flat battery. The HAT cuts power on its own when the
  pack is exhausted; a clean `poweroff` at 3150 mV per cell would need a root service and is
  left out. The UI warns once when the pack is at or below 20 % or any cell is under 3150 mV.
- The sync thread sets `measurement.synced` while the GUI thread may be saving. Writes are a
  single bool per object, and `save_data` runs again when the thread finishes, so the file
  ends consistent. A crash mid-sync can re-upload a measurement, never lose one.
- Manual Sync still runs on the GUI thread. It refuses to start while a background sync runs.
- Needs `smbus2` (pip) or `python3-smbus` (apt) and I2C enabled (`raspi-config`).

## Verification

`battery.decode` was checked against hand-built register blocks (discharging: -100 mA, 185 min
to empty; fast charging: +500 mA, 30 min to full). On the Pi: `i2cdetect -y 1` shows `2d`,
and the top bar percentage matches Waveshare's `ups.py`. Unplug the USB-C input: the bolt
disappears and time to empty appears within 10 s. With a token stored, save a scan while
online: the sync dot turns green within a few seconds without tapping Sync.
