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
