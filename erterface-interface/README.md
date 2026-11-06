# ERTERFACE — Coconut Health Field Interface

PyQt6 desktop UI for an ERT device. Field-mode target = Raspberry Pi, 800x480 touch.

## Run

```bash
cd erterface-interface
pip install -r requirements.txt
python app.py
```

On the Pi, double-click `run_erterface.sh` (or a Desktop launcher whose
`Exec=` points at it). It runs `app.py` with the thesis repo's `../.venv`
and logs to `erterface.log`.

## Modes

```bash
# Drive sync disabled
ERTERFACE_DRIVE_MODE=off python app.py

# Drive sync via local staging folder (./drive_staging/) — no Google auth needed
ERTERFACE_DRIVE_MODE=local python app.py

# Real Google Drive (default). First run opens browser for OAuth.
python app.py
```

## Where things go

- `app.py` — entrypoint
- `src/erterface/` — package (app, models, widgets, scan view, export, drive sync)
- `plantation_data.json` — runtime data (created on first save)
- `data/` — per-measurement `.npy` + `.png` artifacts
- `exports/` — auto-exported CSV snapshots
- `drive_staging/` — Drive test-mode payloads
- `assets/fonts/` — drop Hanken Grotesk + Geist `.ttf` here for branded typography
- `~/.config/erterface/` — Drive OAuth tokens + client secret

## Docs

- `SPEC.md` — full spec (objective, architecture, boundaries)
- `AGENTS.md` — repo-local agent instructions

## Battery and auto-sync (Pi)

- Battery: Waveshare UPS HAT (E). Enable I2C (`sudo raspi-config` → Interface → I2C),
  `pip install smbus2` (or `sudo apt install python3-smbus`), check `i2cdetect -y 1` shows `2d`.
  The top bar then shows charge, time to empty, and a bolt while charging. Without the HAT
  it shows nothing.
- Auto-sync: once Drive is signed in (Sync → setup), new scans upload in the background
  after saving and every 5 minutes whenever the Pi is online. Offline scans wait and go up
  later; the sync dot's tooltip says how many are waiting. See ADR-0084.
- Clean poweroff on a flat pack: `sudo pi/install_ups_service.sh` once per Pi. When a cell
  stays under 3150 mV for 60 s without charging, the Pi shuts down cleanly and powers back
  on when USB-C is plugged in. The top bar counts down first; plugging in cancels it.
  Logs: `journalctl -u erterface-ups -f`. See ADR-0085.
- Sync (button or automatic) never freezes the screen; it uploads in the background.
