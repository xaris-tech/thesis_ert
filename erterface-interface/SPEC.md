# Spec: ERT Coconut Health Field Interface (v2)

> **Superseded in part (2026-10-25):** scanning is no longer a stub. The scan
> screen is `CaptureScreen`, which embeds the thesis repo's capture session;
> `ScanWorker`, `classify_from_max` and the live mode of `ScanView` are gone,
> and `ScanView` is only the read-only review of a saved measurement. See
> AGENTS.md for the current contract. Sections below mentioning `ScanWorker`
> describe the earlier stub.

## Diff vs. v1 (this revision)

| Change | Reason |
| --- | --- |
| **Cut:** manual Measurement add/edit (dialog path). Measurements are created by ScanView only. | Your scope call. Removes the QDateTime→string crash in `dialogs.get_data()`. |
| **Cut:** `AddEntityDialog` `Measurement` branch and the Measurement fields branch in `edit_entity`. | Same. |
| **Card layout:** `CardWidget` is a `QFrame` with a body region (clickable) and an action row (real buttons). | Fixes nested-`QPushButton` event capture + 5-button overflow on 230 px cards. |
| **Validation:** every Add/Edit dialog blocks `accept()` if required fields are empty or duplicate within the parent. Inline error label, not a popup. | Your call. Matches "empty plantation name should not be possible." |
| **Error handling:** no `except: pass` on data paths. Failures surface in top-bar `lbl_status`; dialog validation uses an inline `QLabel` error row. Popups reserved for destructive confirms (delete, exit). | Your call. Field device must not crash on transient disk errors. |
| **Close path:** `closeEvent` saves once, exports once, runs sync once — each guarded by a status label on failure, not a bare `except`. | Bug fix. |
| **Top bar:** labels shortened ("12:34" not "Time: 12:34"); status label has `stretch=1` already; verify all four buttons fit at 800 px. | Bug fix for clipped buttons. |
| **Status pill + heatmap:** kept. Pill colors per `theme.status_color`. `RdYlBu_r` tomogram. | Implicit keep (core to classification read). |
| **Open questions** in v1 are now resolved rules (Fonts, Scan back, Drive folder). | Spec is the source of truth, not a discussion doc. |
| **Success criteria** rewritten as testable, mechanical checks. | Reviewable. |

---

## Objective

Ship a working PyQt6 desktop interface for an ERT (Electrical Resistivity
Tomography) field device that classifies coconut tree health. Operated by
**field workers** on a **Raspberry Pi with an 800x480 touch display** (gloved
fingers, sunlight, no keyboard, no mouse).

The reference look is in `precision_arboreal_system/DESIGN.md` (structural
tokens only — typography, 8 px grid, radii) and the four HTML/Tailwind screen
mockups in `plantation_dashboard/`, `scan_interface/`, `tree_selection/`,
`zone_selection/`. **HTML mockups are reference, not source.**

Real ERT hardware is **out of scope**. `ScanWorker` is a stub; the
`scan_complete(matrix, max_value, npy_path, png_path)` signal is the contract.

### User stories

- As a field worker, I navigate Plantation > Zone > Tree > Measurement with
  one tap per level, see the current path as breadcrumbs, and back out via
  Home or a breadcrumb tap.
- As a field worker, I add or edit a Plantation / Zone / Tree from a single
  dialog that adapts to the current level. Required fields are validated
  inline; I cannot save an empty or duplicate entry.
- As a field worker, when I select a Tree I can launch a scan from a
  dedicated full-screen scan view, watch progress, and see a new Measurement
  card appear in the Tree's history when the scan finishes.
- As a field worker, I can search and sort cards at any level and manually
  reorder them.
- As a field worker, I read each Measurement's classification (HEALTHY /
  AT_RISK / UNHEALTHY) and impedance ratio at a glance.
- As a field worker, I can switch the app between light and dark mode for
  daylight vs. canopy conditions.
- As a field worker, all text input happens through an on-screen keyboard.

### Non-goals (v2)

- Real ERT hardware integration (stub only).
- Authentication, multi-user, backend services.
- Cloud sync targets beyond Google Drive.
- Manual Measurement add/edit. Measurements are created by scans.
- Internationalization.
- Automated tests (`py_compile` is the only CI check).
- Production packaging (PyInstaller, .deb).

---

## Tech stack

- **Language:** Python 3.10+
- **GUI:** PyQt6 (6.5+)
- **Plotting:** matplotlib `QtAgg` backend, 3"x3" Figure at 80 dpi
- **Numerics:** numpy (scan stub tomogram only)
- **Data:** JSON on local disk + `.npy` / `.png` per measurement
- **No web stack, no backend, no network calls beyond Google Drive OAuth**

---

## Commands

```bash
pip install -r requirements.txt
python app.py
ERTERFACE_DRIVE_MODE=local python app.py    # writes Drive payloads to ./drive_staging/
ERTERFACE_DRIVE_MODE=off python app.py      # disable Drive sync
python -m py_compile $(git ls-files '*.py') # CI check
```

No build, no lint, no test runner, no formatter. `pip install` + `python app.py`
is the developer loop. `py_compile` is the CI gate.

---

## Project structure

```
app.py                       # Entrypoint: imports from src.erterface and runs QApplication
SPEC.md                      # This document
AGENTS.md                    # Repo-local agent instructions
requirements.txt             # PyQt6, numpy, matplotlib, google-api-python-client, google-auth-oauthlib, requests

src/erterface/               # Package
  __init__.py
  app.py                     # CardApp(QMainWindow) — main window, scan view push/pop
  models.py                  # Plantation, Zone, Tree, Measurement + to_dict/from_dict
  workers.py                 # ScanWorker(QThread) — stub, real-device contract
  paths.py                   # DATA_FILE, DATA_DIRECTORY, runtime dirs
  theme.py                   # apply_theme, fonts, design tokens, color constants
  dialogs.py                 # AddEntityDialog(QDialog) — Plantation/Zone/Tree add/edit only
  scan_view.py               # ScanView(QWidget) — full-screen scan flow
  export.py                  # export_measurements_csv(path) — one row per measurement
  drive_sync.py              # DriveClient — OAuth InstalledApp + local-staging
  errors.py                  # status_toast(parent, text, level) — single error-render path
  widgets/
    __init__.py
    card.py                  # CardWidget(QFrame) — body clickable, action row buttons
    plot.py                  # TomogramPlot(FigureCanvas)
    keyboard.py              # TouchLineEdit(QLineEdit), VirtualKeyboard(QDialog)

precision_arboreal_system/DESIGN.md
plantation_dashboard/        # Reference: HTML mockup + screenshot
scan_interface/              # Reference: HTML mockup + screenshot
tree_selection/              # Reference: HTML mockup + screenshot
zone_selection/              # Reference: HTML mockup + screenshot

plantation_data.json         # Runtime, gitignored
data/                        # Runtime, gitignored
drive_staging/               # Local-staging Drive test mode, gitignored
exports/                     # Auto-export on close, gitignored
~/.config/erterface/         # Drive OAuth credentials (user-specific, NOT in repo)
```

---

## Domain model

`Plantation > Zone > Tree > Measurement`. `Measurement` is a leaf.

| Class        | Identity field    | Children                | Notes                                    |
|--------------|-------------------|-------------------------|------------------------------------------|
| Plantation   | `plant_id`        | `zones: list[Zone]`     | `name` for display                       |
| Zone         | `zone_id`         | `trees: list[Tree]`     |                                          |
| Tree         | `tree_id`         | `measurements: list[M]` |                                          |
| Measurement  | (no id)           | none                    | `imp_ratio`, `classification`, `timestamp`, `data_path`, `image_path`, `synced` |

`Measurement` instances are constructed **only** in `ScanView._on_scan_complete`.
There is no UI to create or edit a Measurement by hand.

Persistence:
- `plantation_data.json` at repo root.
- `data/` holds per-measurement `.npy` + `.png`.
- `CardApp.save_data()` is atomic: `tmp` → `flush` → `fsync` → `os.replace`.
  On failure it routes through `errors.status_toast(...)` and **does not**
  raise.
- `load_data()` failures show a modal `QMessageBox.warning` (one-time) and
  reset `database = []`; `navigation_path` is also cleared.

JSON format is identical to v1 — no migration.

---

## Validation rules (Plantation / Zone / Tree)

Enforced in `AddEntityDialog.accept()` override, before super().accept():

| Rule | Plantation | Zone | Tree |
| --- | --- | --- | --- |
| `name` non-empty after `.strip()` | required | n/a (display name = `Zone <id>`) | n/a (display name = `Tree <id>`) |
| `id` non-empty after `.strip()` | required | required | required |
| `id` unique within parent | required (no other Plantation with same `plant_id`) | required (no other Zone in same Plantation with same `zone_id`) | required (no other Tree in same Zone with same `tree_id`) |
| `id` matches `[A-Za-z0-9_\-]{1,32}` | recommended (warn, do not block) | required (block) | required (block) |

If validation fails, the dialog stays open and an inline `QLabel` error row
shows the first failing rule in red (`#DA3633`). `accept()` is not called.
`QDialog.DialogCode.Accepted` is only returned on a clean accept.

Edit mode re-runs the same rules but excludes the entity's own current id
from the duplicate check.

---

## Error handling

Single render path: `errors.status_toast(parent, text, level)` writes to
`parent.lbl_status` and (for warnings/errors) briefly highlights it. No
popups except for the three cases below.

| Event | Render |
| --- | --- |
| `save_data` failure | `status_toast("Save failed: <reason>", "error")` |
| `load_data` failure | `QMessageBox.warning` (one-time at startup) |
| CSV export failure (manual or auto) | `status_toast("Export failed: <reason>", "error")` |
| Drive sync failure (manual or auto) | `status_toast("Sync failed: <reason>", "error")` |
| `ScanWorker.scan_error` | `QMessageBox.warning` (user-initiated action, deserves attention) |
| Delete confirmation | `QMessageBox.warning` (destructive, irreversible within the run) |
| Exit confirmation | `QMessageBox.question` (destructive, irreversible) |
| Validation failure in `AddEntityDialog` | Inline `QLabel` in the dialog |

Forbidden:
- `except Exception: pass` on any data path.
- Popups for non-destructive, non-user-initiated failures.
- Raising from `closeEvent` — the app must close.

`closeEvent` order: save → auto-export → auto-sync. Each step's outcome is
reported in `lbl_status`; the next step still runs.

---

## UI architecture

`CardApp` is a `QMainWindow` (800x480). Top bar, breadcrumb row, search +
sort row, scrollable card grid, FAB. Scan view is pushed onto a
`QStackedWidget`.

### Top bar (min height 48 px)

`12:34 | 25 GB free (87%) | <status> ... [Export CSV] [Sync Drive] [Dark] [Exit]`

- Time: `HH:mm` only (saves horizontal space). Updated every second.
- Storage: `shutil.disk_usage("/")` summary, unchanged content but shorter
  prefix. "Unknown" fallback stays.
- Status label: `stretch=1`, ellipsizes, takes the slack.
- Buttons: `Export CSV` (green), `Sync Drive` (blue), `Dark`/`Light`
  (neutral), `Exit` (red). All 40 px tall, 12 px bold font.

At 800 px the row fits because Time is `12:34` not `Time: 2026-...`. Smoke
test: resize the window to 800 px and confirm all four buttons are fully
visible without horizontal scroll.

### Breadcrumb row

`Home > PlantationName > ZoneName > TreeName`. Each segment except the last
is a tappable button that navigates there. Last segment is a static label.

### Search + sort row

`TouchLineEdit` (search, placeholder "Search by name or ID...") + `QComboBox`
with four modes: `Sort: Manual Order`, `Sort: Newest First`, `Sort: A-Z`,
`Sort: Z-A`. Reorder arrows show only when Manual + search empty.

### Card grid

`QGridLayout` in a `QScrollArea` with `QScroller` (touch scroll, both bars
off). 3 columns, 230x160 cards, 15 px spacing, 20/10/20/20 margins. Card
classes per entity. Card has 8 px corner radius. No card overflows the
800x480 viewport — content can scroll, the grid cannot.

### Card layout (v2 — replaces v1's nested QPushButton)

```
CardWidget(QFrame)  230x160
├── body region (mousePressEvent → emit clicked signal)
│   ├── title row  (title label)
│   └── (Measurement) thumbnail + date/time + pill + ratio
└── action row  (QHBoxLayout of real QPushButtons)
    ├── ◀  (only if reorder_enabled)
    ├── Scan  (only for Tree)
    ├── Edit
    ├── Delete
    └── ▶  (only if reorder_enabled)
```

- Card body is the click target. Tapping anywhere outside an action button
  fires `card_clicked(data_object)`.
- Action buttons consume their own clicks and never bubble up to the body.
- Reorder arrows are visible only when sort == Manual and search is empty.
- Measurement cards show a thumbnail (or placeholder if `.png` missing),
  date, time, status pill, and ratio. No action buttons except the body
  tap, which pushes `ScanView` in review mode: the same scan screen,
  filled from the saved measurement, with a Sync Status readout and a
  single Back button.

### FAB

60x60 `+` button, solid black, bottom-right, overlaid on the scroll area.
Hidden when the current level is `Measurement` (which has no children).

### Theme

`is_dark_mode` is in-memory only. `apply_theme()` rebuilds stylesheet strings
for the window, top bar, search/combo, cards, and FAB. Light bg `#f2f4f7`,
dark bg `#121212`. FAB is solid black in both modes. Theme toggle rebuilds
`ScanView` from scratch via `_rebuild_scan_view()`.

### Text input

All human text input goes through `TouchLineEdit`. It pops a frameless
760x380 `VirtualKeyboard` dialog on focus. Never use raw `QLineEdit` for
user-entered text.

---

## Dialogs

`AddEntityDialog(QDialog)` handles Plantation, Zone, and Tree add/edit.
There is no Measurement dialog in v2.

- Form fields swap by `level_name`.
- Edit mode pre-fills from `current_data`.
- Required fields are marked with a trailing `*` in the label.
- Inline error `QLabel` below the form shows validation messages.
- `accept()` is overridden: if validation fails, it sets the error label
  and returns without calling `super().accept()`.
- Dialog result codes: check with `in (QDialog.DialogCode.Accepted, 2)`.
  The `2` is the legacy integer for Accepted; preserve.

Field set per level:

| Level | Fields |
| --- | --- |
| Plantation | `name *`, `Plantation ID *` |
| Zone | `Zone ID *` |
| Tree | `Tree ID *` |

---

## Scan flow

`ScanView(QWidget)` is a full-screen view pushed onto the `QStackedWidget`.
It carries its own `← Back` button in its own top bar; emits
`back_requested` and `measurement_created(object)`.

- On Run: starts `ScanWorker(self.tree.tree_id)`. Worker emits
  `scan_progress(int)`, `scan_complete(matrix, max_value, npy_path, png_path)`,
  `scan_error(str)`.
- On success: `ScanView` derives classification from `max_value` via
  `classify_from_max`, renders the matrix in `TomogramPlot`, and switches
  the Run button to "Done". Clicking Done appends a new `Measurement` to
  the parent tree, calls `save_data()`, and pops the view.
- On error: status reverts; `QMessageBox.warning` shows the message.
- On Cancel or Back: worker is stopped, view pops, no measurement created.

Classification mapping (`scan_view.classify_from_max`):
- `max_value < 0.5` → `"UNHEALTHY"`
- `0.5 <= max_value < 1.5` → `"AT_RISK"`
- `max_value >= 1.5` → `"HEALTHY"`

Hardware contract — preserve:
`scan_complete.emit(self.data_matrix, max_value, file_path_npy, file_path_png)`.

---

## Data export (CSV)

`export.export_measurements_csv(database, path)` — one row per measurement.

Columns: `plantation_id, plantation_name, zone_id,
tree_id, measurement_timestamp, imp_ratio, classification,
data_path, image_path, synced`.

Trigger points:
- **Manual:** top-bar "Export CSV" button → `QFileDialog.getSaveFileName` →
  write. Default name `plantation_export_<YYYYMMDD_HHMMSS>.csv`. On
  failure: `status_toast(...)`.
- **Auto:** on `closeEvent`, write to
  `./exports/plantation_export_<YYYYMMDD_HHMMSS>.csv` if any measurement
  exists. On failure: `status_toast(...)`. The next step (sync) still runs.

Atomicity: `*.tmp` → `os.replace`, same pattern as `save_data()`.

---

## Google Drive sync

`ERTERFACE_DRIVE_MODE` env var: `oauth` (default), `local`, `off`.

- `oauth` — real Drive via OAuth 2.0 InstalledApp flow. Refresh token at
  `~/.config/erterface/drive_credentials.json`.
- `local` — writes would-be uploads to `./drive_staging/` with the same
  folder structure. Dev/test.
- `off` — sync is a no-op. Export still works.

Per-measurement upload path:
`<plantation_id>/<zone_id>/<tree_id>/measurement_<ts>.{npy,png,json}`.

Sync state: `Measurement.synced: bool`. Flipped to `True` on success; then
`save_data()` is called.

Auth setup (one-time): OAuth Desktop client JSON at
`~/.config/erterface/drive_client_secret.json`. Optional folder id at
`~/.config/erterface/drive_config.json` (key: `folder_id`). If the secret
file is missing and mode is `oauth`, `sync_drive` shows a
`QMessageBox.warning` with setup instructions and returns without
uploading. The auto-sync on `closeEvent` does **not** show a popup — it
falls back to a `status_toast` and lets the app close.

Scopes: `https://www.googleapis.com/auth/drive.file`.

`sync_unsynced(database, client=None, progress_cb=None, cancel_check=None)`
returns `(uploaded, failed, skipped)`.

---

## Classification (visual)

- `HEALTHY` — green pill `#2EA043`
- `AT_RISK` — amber pill `#D4A017`
- `UNHEALTHY` — red pill `#DA3633`

Pill text white, uppercase, 12 px bold. Defined in `theme.status_pill_style`.

Tomogram heatmap: `RdYlBu_r` colormap, `vmin=0`, `vmax=2.5`. Background
`#f9f9f9` (light) / `#1e1e1e` (dark).

---

## Code style

Match the existing `based-3.py` style:

- 4-space indent, no tabs.
- One class per top-level concern, no inheritance for sharing style.
- Type hints optional; the existing file uses none.
- `QMainWindow` / `QDialog` subclasses call `super().__init__(parent)`
  first, then build widgets, then connect signals.
- Inline stylesheet strings (`setStyleSheet(f"""...""")`); no external QSS.
- No comments unless asked. No docstrings on new code unless they explain a
  non-obvious contract.
- Constants (paths, sizes) live in `paths.py` and `theme.py` — not in
  module scope of `app.py`.
- `CardWidget` is a `QFrame` subclass (not `QPushButton`). Action buttons
  inside it are real `QPushButton` children.

Example shape (illustrative, not real code):

```python
# src/erterface/widgets/card.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QPushButton

from ..models import Measurement, Tree, Zone


class CardWidget(QFrame):
    def __init__(self, title, data_object, on_body_click, on_edit, on_delete,
                 on_move_left, on_move_right, on_scan, is_dark_mode,
                 reorder_enabled):
        super().__init__()
        self.data_object = data_object
        self.setFixedSize(230, 160)
        ...
```

---

## Design system tokens

Adopt the structural parts of `precision_arboreal_system/DESIGN.md`:

- **Typography:** Hanken Grotesk (headlines/body), Geist (technical labels).
  Load via `QFontDatabase.addApplicationFont` from `./assets/fonts/` if
  present, else fall back to system sans-serif. Sizes follow DESIGN.md:
  32/24/18/16/14/12.
- **Grid:** 8 px baseline. Card grid: 3 columns, 15 px gutters, 20 px outer
  margins, 10 px top margin.
- **Radii:** 4 px buttons/inputs, 8 px cards.
- **Cards:** 230x160 px.

Color rules (per user direction, overriding the "grayscale only" clause in
DESIGN.md):

- **Status pill (classification):** green/amber/red per `theme.status_color`.
- **Tomogram heatmap:** `RdYlBu_r`.
- **All other UI elements:** standard surface colors per
  `precision_arboreal_system/DESIGN.md` (light bg `#faf9f9` / dark bg
  `#121212`, with mid-tones for cards and inputs). CardApp uses
  `LIGHT_BG = "#f2f4f7"` per v1; that override stands.

---

## Testing strategy

No automated tests this round. Manual smoke checklist is the success gate:

- [ ] `python app.py` launches at 800x480; top bar shows time, storage,
      status, and all four buttons fully visible.
- [ ] FAB tap opens Add Plantation dialog. Empty name + empty ID → "Save"
      blocked, inline error shown.
- [ ] Valid Plantation created, then drilling in shows its Zones.
- [ ] Add Zone: empty ID → blocked. Duplicate ID (same Plantation) →
      blocked. Valid Zone created.
- [ ] Add Tree: empty ID → blocked. Duplicate ID (same Zone) → blocked.
      Valid Tree created.
- [ ] Tap a Tree card's body (not an action button) drills into
      Measurements (empty list).
- [ ] Tap Tree card's `Scan` button → ScanView appears with
      `← Back` / `Run scan` / `Cancel` visible and tappable.
- [ ] Tap `Run scan` → progress bar advances, classification + ratio
      readouts populate, tomogram renders, button switches to `Done`.
- [ ] Tap `Done` → view pops, new Measurement card appears in Tree view
      with date, time, pill, ratio, thumbnail.
- [ ] `Cancel` mid-scan → worker stops, view pops, no measurement.
- [ ] Tap a Measurement card → read-only details dialog shows
      classification, ratio, timestamp, sync state, file paths.
- [ ] Search filters cards in real time.
- [ ] Sort modes re-order the grid; reorder arrows appear only in Manual
      + empty search.
- [ ] Theme toggle flips light/dark without restart; `ScanView` is
      rebuilt and matches the new theme.
- [ ] Open on-screen keyboard by tapping the search bar; type and commit
      with Done.
- [ ] Restart the app; previously created entities reload from
      `plantation_data.json`.
- [ ] `ERTERFACE_DRIVE_MODE=local` + manual Sync → files appear in
      `./drive_staging/<plantation_id>/<zone_id>/<tree_id>/`. Measurement
      `synced` flag flips to `True`.
- [ ] Close app: `save_data` → auto-export CSV to `./exports/` → auto-sync
      runs. Status label shows results of each.
- [ ] `python -m py_compile $(git ls-files '*.py')` exits 0.

CI: `py_compile` is the only automated check.

---

## Boundaries

- **Always:**
  - Run the smoke checklist above before claiming a change is done.
  - Preserve the atomic save pattern (`tmp` → `flush` → `fsync` →
    `os.replace`) in `CardApp.save_data()`.
  - Preserve the `scan_complete(matrix, max_value, npy_path, png_path)`
    signal signature in `ScanWorker`.
  - Use `TouchLineEdit` for all human text input.
  - Check dialog results with `in (QDialog.DialogCode.Accepted, 2)`.
  - Route all error UI through `errors.status_toast` unless the
    "Popups allowed" table in the Error handling section says otherwise.
  - Preserve the existing JSON data format — no schema migration.

- **Ask first:**
  - Adding a runtime dependency beyond PyQt6 / numpy / matplotlib /
    google-api-python-client / google-auth-oauthlib / google-auth /
    requests.
  - Changing the on-disk data format or file paths.
  - Changing the `ScanWorker` signal signature or the classification
    mapping rules.
  - Replacing the entrypoint or breaking the `app.py` name.
  - Adding user-facing strings that need translation later.

- **Never:**
  - Add network calls, auth, or a backend service of any kind beyond
    Google Drive sync as specified.
  - Bypass the `to_dict` / `from_dict` round-trip when persisting models.
  - Mutate widgets in place; always go through `refresh_ui()`.
  - Use raw `QLineEdit` for user text input on the main screens.
  - Edit or commit `plantation_data.json` or anything under `data/`,
    `drive_staging/`, `exports/`.
  - Modify the HTML mockups or `screen.png` files — reference only.
  - Use `except Exception: pass` on any data path.
  - Raise from `closeEvent`.
  - Bring back the manual Measurement add/edit dialog.

---

## Resolved questions (v1 open questions, now decided)

- **Fonts on Pi:** load from `./assets/fonts/` if present, else system
  fallback. Bundling is a deployment step, not a code step.
- **Scan view back affordance:** the scan view carries its own back
  button in its own top bar. Main top bar has no back button.
- **Drive target folder:** folder id from
  `~/.config/erterface/drive_config.json` (key: `folder_id`). If absent
  in `oauth` mode, sync falls back to the user's Drive root.
