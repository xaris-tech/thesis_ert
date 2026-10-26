# AGENTS.md

PyQt6 desktop frontend for an ERT (electrical resistivity tomography) device that classifies coconut tree health. No backend server in this repo — sync target is Google Drive via OAuth.

## Entry point

- Entrypoint: `/home/rantiche/erterface/app.py`. Run: `python app.py` from the repo root.
- App code lives in `src/erterface/`. `app.py` is a thin launcher that imports `CardApp` from there.
- `based-3.py` is the legacy single-file version. Don't edit it — refactor target is `src/erterface/`.
- Install: `pip install -r requirements.txt` (PyQt6, numpy, matplotlib, google-api-python-client, google-auth-oauthlib, google-auth, requests).
- Window is hard-coded **800x480** (Raspberry Pi / touch field mode). Keep controls touch-sized (min-height ~40-45px, 14-18px fonts).
- No test framework yet. `py_compile` is the only CI check.

## Repo layout

- `app.py` — entrypoint
- `import_scans.py` — rebuilds `plantation_data.json` from `<thesis root>/scans`: plantation **Saline** (trees = tank positions: empty, e1..e12, pairs e1-e7..e6-e12, centre; from the position-series labels and the SSIM/wood-at target text) and **Discs** (disc-01..). Backs up the old file to `data/`, pre-builds card thumbnails in `data/thumbs/`. `--dry-run` lists what it would import.
- `src/erterface/` — the package
  - `app.py` — `CardApp(QMainWindow)` (main window, scan push/pop, export/sync triggers)
  - `models.py` — `Plantation`, `Tree`, `Measurement`, `iter_all_measurements()` (yields `(plantation, tree, measurement)`)
  - `paths.py` — runtime paths + classification constants
  - `theme.py` — colors, fonts, status pill helper
  - `capture_screen.py` — `CaptureScreen(QWidget)`: the scan screen. Embeds the thesis repo's capture session (`tree_ert.qt.main_window.MainWindow`, `compact=True`) under a farm header with Back / Save to tree
  - `dialogs.py` — `AddEntityDialog` + `make_entity()` factory
  - `scan_view.py` — `ScanView(QWidget)` (read-only review of one saved measurement, opened by tapping a measurement card)
  - `export.py` — `export_measurements_csv(database, path)` (one row per measurement)
  - `drive_sync.py` — `DriveClient` + `sync_unsynced()` (OAuth / local / off modes)
  - `widgets/card.py` — `CardWidget` (generic card, measurement variant with thumbnail + pill)
  - `widgets/keyboard.py` — `TouchLineEdit` + `VirtualKeyboard`
  - `widgets/plot.py` — `TomogramPlot`
- `plantation_dashboard/`, `scan_interface/`, `tree_selection/`, `zone_selection/` — **HTML/Tailwind web mockups** + reference screenshots. Visual reference, not source.
- `precision_arboreal_system/DESIGN.md` — design system spec. Color constraint is intentionally **disregarded** — see SPEC.md. Structural tokens (typography, 8px grid, radii) are still followed.
- `requirements.txt`, `.gitignore`, `SPEC.md`, `AGENTS.md` at repo root.

## Domain model

Hierarchy: `Plantation > Tree > Measurement` (the Zone level was removed 2026-10-26; old files load with each zone's trees lifted into the plantation). `Measurement` is a leaf. A tree's name is its ID (`disc-01`, `e1`, `T003`).

- Each class has `to_dict` / `from_dict` for JSON. Don't bypass when persisting.
- IDs: `Plantation.plant_id`, `Tree.tree_id`. `Measurement` has no id.
- `Measurement` carries `imp_ratio`, `classification` (`HEALTHY` / `AT_RISK` / `UNHEALTHY`), `timestamp`, `data_path` (`.npy`), `image_path` (`.png`), `synced: bool` (Drive sync state).
- Measurements saved from the capture session are `UNCLASSIFIED` with `imp_ratio = None`: the instrument produces images, not a health verdict. `data_path` is the run folder under `<thesis root>/scans/runs/`, `image_path` its `reconstruction.png` (else `absolute.png`). Older measurements may still carry HEALTHY / AT_RISK / UNHEALTHY and a `.npy`.
- Drilldown: `CardApp.navigation_path` (list of model objects). `get_current_list()` derives the current view; `get_current_level_name()` derives the level to add.

## Persistence

- `plantation_data.json` at repo root. `data/` holds per-measurement `.npy` + `.png`.
- `CardApp.save_data()` is atomic: `tmp` → `flush` → `fsync` → `os.replace`. **Preserve.**
- `CardApp.load_data()` runs in `__init__`; failures show `QMessageBox.warning` and start with `database = []`.
- Data format is identical to the legacy `based-3.py` — no migration needed for existing files.

## UI architecture

- `CardApp` is a `QMainWindow` with a `QStackedWidget` that holds the index page and one pushed screen (`CaptureScreen` or `ScanView`).
- `CardApp.refresh_ui()` is the single rebuild entry point: breadcrumbs + clear cards + populate + FAB visibility. After any state change, call `refresh_ui()` (and `save_data()` for mutations). Don't mutate widgets in place.
- Top bar: time | storage | status | Export CSV | Sync Drive | theme toggle | Exit. Min height 48px.
- Breadcrumb row, search + sort row, then scrollable card grid (3 cols, 230x160, 15px spacing, 20/10/20/20 margins) with a 60x60 "+" FAB bottom-right. `QScroller` for touch scroll, both bars off.
- Reorder arrows (`◀`/`▶`) on `CardWidget` only when `reorder_enabled` (sort = Manual Order, search empty).
- Tree cards get a "Scan" button alongside Edit / Delete that pushes the `CaptureScreen` for that tree.
- Theme: `is_dark_mode` is in-memory only. `apply_theme()` rebuilds stylesheet strings. Light bg `#f2f4f7`, dark `#121212`. FAB is solid black in both modes.
- Text input rule: use `TouchLineEdit` (not raw `QLineEdit`) for human-typed text. It pops a 760x380 frameless `VirtualKeyboard` on click.

## Scan flow

- `CaptureScreen` embeds the capture session; capture, settings, conditions, run recording and reconstruction gates are all the capture session's (see the thesis repo's CLAUDE.md / AGENTS.md). It pre-fills the specimen ID from the tree (`T002` → `coconut-tree-2`) and opens in demo mode when no USB serial device is attached.
- `MainWindow.run_finished(run_path)` enables Save to tree, which emits `measurement_created`; `CardApp` appends it to the screen's tree and saves.
- Both pushed screens emit `back_requested` / `measurement_created` and have `shutdown()`; `CaptureScreen.shutdown()` closes the session (cancels a capture, saves instrument settings, closes the session log).
- Hardware contract: keep `scan_complete.emit(self.data_matrix, max_value, file_path_npy, file_path_png)` — that's the wire format for the real device integration.

## Data export (CSV)

- `export.export_measurements_csv(database, path)` — one row per measurement. Columns: `plantation_id, plantation_name, tree_id, measurement_timestamp, imp_ratio, classification, data_path, image_path, synced, pattern`.
- Manual trigger: top-bar "Export CSV" button → `QFileDialog.getSaveFileName` → write. Atomic via tmp + `os.replace`.
- Auto trigger: `closeEvent` writes `./exports/plantation_export_<ts>.csv` if any measurement exists.

## Google Drive sync

- `ERTERFACE_DRIVE_MODE` env var: `oauth` (default, real Drive), `local` (writes to `./drive_staging/` — for dev), `off` (disable).
- `DriveClient` uses OAuth 2.0 InstalledApp flow (`google-auth-oauthlib`). First run opens browser; refresh token stored at `~/.config/erterface/drive_credentials.json`.
- Setup: drop OAuth Desktop client JSON at `~/.config/erterface/drive_client_secret.json`. Optional folder id in `~/.config/erterface/drive_config.json` (key: `folder_id`).
- Scopes: `https://www.googleapis.com/auth/drive.file` (narrow — files the app creates).
- Per measurement upload: `<plantation_id>/<tree_id>/measurement_<ts>.{npy,png,json}`.
- Sync state: `Measurement.synced` flipped to `True` on success; `save_data()` called.
- Manual trigger: top-bar "Sync Drive" button. Auto trigger: `closeEvent` runs a sync pass (skipped if mode == `off`).
- `sync_unsynced(database, client=None, progress_cb=None, cancel_check=None)` returns `(uploaded, failed, skipped)`.

## Conventions to keep

- One `AddEntityDialog` for all four entity types; swaps form fields by `level_name`.
- Dialog result codes: check with `in (QDialog.DialogCode.Accepted, 2)` — the `2` is the legacy integer for Accepted.
- Card grid: 3 columns, 230x160 cards, 15px spacing, 20/10/20/20 margins.
- Min control height 40-45px, font 14-18px (touch + 800x480).
- No comments added on new code unless asked.
- Atomic file writes (tmp + `os.replace`) for `plantation_data.json` and CSV exports.

## Things the agent would likely miss

- The `*/code.html` files are web mockups, not Python source. Don't port them.
- "Storage" label shows `shutil.disk_usage("/")` — fine on Pi, misleading elsewhere.
- `Measurement` cards branch on `isinstance(data_object, Measurement)` in `CardWidget` — different layout (thumbnail + date/time/pill/ratio).
- Saved `data_path`/`image_path` may be Windows paths from another machine; always read them through `paths.resolve_data_file`, which falls back to the same file name under `data/`.
- Field/touch rules: colours come from `theme.palette()` (light = sunlight theme; status pills clear 4.5:1 with white text); touch targets are `theme.TOUCH_MIN` (44 px); no `:hover` styles (hover sticks after a tap on a touchscreen); buttons are `NoFocus`.
- Performance rules: don't import matplotlib at startup (`widgets/plot.py` is imported only where a tomogram is drawn); card styling is one `card_stylesheet()` on the grid container, not per card; thumbnails go through `QPixmapCache`; search is debounced (180 ms); the capture session is pre-imported on a background thread at startup.
- The on-screen keyboard docks into the nearest ancestor with a `keyboard_holder` (`AddEntityDialog`, `CardApp` for search) and writes keys straight into its field; Cancel restores the original text.
- On a screen ≤800x480 (the 7" Pi display) `app.py` opens fullscreen; `--fullscreen` forces it elsewhere. Under the 48 px top bar a pushed view has 800x432.
- `ScanView` is rebuilt (not just re-themed) on theme toggle (`CardApp._rebuild_scan_view`). `CaptureScreen` is not rebuilt — that would cancel a capture — and the capture session stays light-themed.
- `closeEvent` does save + auto-export + auto-sync. Don't bypass — that's where data leaves the device.
- Google Drive auth requires `~/.config/erterface/drive_client_secret.json` on first run. Missing file → `QMessageBox.warning` with setup instructions; sync falls back to no-op for that run.
