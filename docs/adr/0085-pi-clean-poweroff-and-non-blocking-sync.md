# ADR-0085: Power the Pi off cleanly on a flat pack, and never block the UI on Drive

- **Status:** Accepted
- **Date:** 2026-11-06
- **Affects:** `erterface-interface/pi/` (new), `erterface-interface/src/erterface/battery.py`, `erterface-interface/src/erterface/app.py`
- **Related:** ADR-0084 (UPS battery reading and background Drive sync)

## Context

ADR-0084 left two gaps. First, nothing powered the Pi off before the UPS HAT (E) cut power at
an empty pack. A hard cut can corrupt the SD card, and it lands mid-write on
`plantation_data.json` or a capture's `frames.csv`. Second, the manual **Sync** button still
uploaded on the GUI thread, freezing the touch screen for the whole upload. The close handler
also ran a blocking sync, which could overlap a background one or stall offline.

## Decision

A root systemd service (`erterface-ups.service`, `pi/ups_shutdown.py`) polls the HAT every 2 s.
When any cell stays under 3150 mV with less than 50 mA of charge current for 60 s, it arms the
HAT to power the Pi back on when USB-C returns (register 0x01 <- 0x55) and runs
`systemctl poweroff`. While the countdown runs, it publishes the deadline at
`/run/erterface-ups/shutdown-at`; the UI shows it every second, saves the farm database once,
and says when a charger cancels it. Manual Sync uses the same worker thread as auto-sync. The
close-time sync is skipped when a worker is busy, when it would need an OAuth prompt, or when
the Pi is offline.

## Rationale

- **A separate root service, not the UI.** `poweroff` needs root, and the guard must run when
  the UI is closed or has crashed. The UI only reads a world-readable file; it gains no
  privilege.
- **Thresholds are Waveshare's** (3150 mV cell, 50 mA, as in `ups.py`), so they match what the
  vendor tests. The demo waits 30 polls of 2 s, which is the same 60 s.
- **`needs_shutdown` lives in `battery.py`** beside `decode`, so the service and any test share
  one rule. `battery.py` imports nothing outside the standard library and `smbus`, so system
  `python3` runs it as root without the venv.
- **A failed I2C read never counts toward a shutdown.** A loose HAT must not power off a Pi
  that is mid-capture on mains.
- **First OAuth sign-in stays on the GUI thread** (setup dialog). Only token-backed uploads go
  to the worker, so no browser window ever opens from a background thread.

## Consequences

- One install step on each Pi: `sudo erterface-interface/pi/install_ups_service.sh`. It enables
  I2C, installs `python3-smbus` when missing, and enables the unit.
- The service unit holds the repo's absolute path. Moving the checkout means re-running the
  installer.
- A capture running at poweroff is cut. Its frames up to that point are already flushed
  (ADR-0023), and the UI warns for 60 s first.
- The sync worker thread is a daemon. Closing the app mid-upload abandons it. Measurements it
  had not saved as synced upload again next session, so the cost is a re-upload, never a loss.

## Verification

`battery.needs_shutdown` returns True for one cell at 3072 mV discharging at -100 mA, and False
for the same cells charging at +500 mA. Offscreen UI checks: during Sync the button is disabled
and re-enabled after; a worker exception shows `Sync failed: ...`; a deadline file shows
`Battery flat: Pi powers off in 41 s` and saves once; removing the file shows the cancellation.
On the Pi, `journalctl -u erterface-ups -f` logs the countdown. Testing the real cut needs a
nearly flat pack: run the Pi on battery until the countdown appears, then plug in USB-C, and
check that it cancels.
