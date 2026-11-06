# Pi setup: UPS battery, clean poweroff, Drive sync

Runbook for the Raspberry Pi 5 field unit with a Waveshare UPS HAT (E). Run each step in
order from the thesis repo root (the directory that contains `erterface-interface/`) and
check its result before moving on. Background: ADR-0084, ADR-0085.

## 1. Get the code

```bash
git checkout rpi
git pull
```

Check: `git log --oneline -1` shows a commit at or after
`feat(erterface): UPS battery icon, clean poweroff, background Drive sync`.

## 2. Install the poweroff service (once per Pi)

```bash
sudo erterface-interface/pi/install_ups_service.sh
```

It enables I2C, installs `python3-smbus` if missing, and enables `erterface-ups.service`.

Check:

```bash
i2cdetect -y 1 0x2d 0x2d     # must show 2d
systemctl is-active erterface-ups   # must print: active
```

If the installer warned "no UPS HAT (E) at I2C 0x2d", I2C was only just enabled:
`sudo reboot`, then run the installer again.

## 3. Make the battery readable from the UI's venv

The UI runs with `.venv/bin/python`.

```bash
.venv/bin/python -c "import smbus2" 2>/dev/null || .venv/bin/python -c "import smbus" \
  || .venv/bin/pip install smbus2
```

Check: this prints the battery state, not `None`:

```bash
cd erterface-interface
../.venv/bin/python -c "from src.erterface import battery; print(battery.read_battery())"
cd ..
```

Compare the percentage with Waveshare's own demo if in doubt.

## 4. Google Drive sync (once per Pi, needs the screen)

1. Put the OAuth Desktop client JSON at `~/.config/erterface/drive_client_secret.json`.
2. Start the UI (`erterface-interface/run_erterface.sh`), tap **Sync**, finish the Google
   sign-in in the browser. This stores `~/.config/erterface/drive_credentials.json`.

After that, scans upload in the background after each save and every 5 minutes whenever
the Pi is online. An agent cannot do the sign-in step; a person must.

Check: tap **Sync**; the status line says `Sync done.` and the dot left of the title is green.

## 5. Final checks

- Top bar shows a battery icon and percentage. Unplug USB-C: the bolt disappears and time
  to empty appears within 10 s. Plug it back in: the bolt returns.
- `journalctl -u erterface-ups -n 20` shows no errors.
- Do **not** test the real shutdown by draining the pack unless asked. When a cell stays
  under 3150 mV for 60 s without charging, the Pi powers off and powers back on when USB-C
  returns. The top bar counts down first, and plugging in cancels it.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No battery icon | smbus missing in `.venv`, or I2C off | Steps 2 and 3 |
| `i2cdetect` shows no `2d` | HAT not seated, or I2C just enabled | Reseat the HAT, reboot |
| Service `failed` | Repo moved after install | Re-run the installer |
| Sync opens setup every time | No stored token | Step 4 |
| Sync dot grey, tooltip "Offline" | No internet | Scans wait and upload when online |
