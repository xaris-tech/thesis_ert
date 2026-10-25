# Plan: ERT v2 Implementation

Spec: `SPEC.md` (v2). This plan turns the spec into 8 reviewable tasks.
Each task touches ≤1 file, has explicit acceptance + verify steps, and is
ordered by dependency.

## Dependency graph

```
T1 errors.py  (new)
  ↓
T2 card.py    (rewrite as QFrame)  ─┐
T3 dialogs.py (validation + cut M) ─┤  parallel-ok
T6 theme.py   (status_pill fix)   ─┘
                ↓
              T4 app.py  (integrate: top bar, error routing, close path,
                          remove Measurement CRUD handling)
                ↓
              T5 scan_view.py  (dead-code, disconnect cleanup)
                ↓
              T7 py_compile gate
                ↓
              T8 manual smoke walkthrough
```

T2, T3, T6 touch separate files and share no state → safe to do in any
order or in parallel. T4 depends on T1+T2+T3+T6 (uses `status_toast`,
new `CardWidget` signature, new dialog API, fixed pill style). T5 is
isolated cleanup, depends on nothing else.

## Tasks

### T1. New module `src/erterface/errors.py`

- **File:** `src/erterface/errors.py` (new)
- **Acceptance:**
  - Exports `status_toast(parent, text, level="info")`.
  - `parent` is a `QMainWindow` (or any object with a `set_status(text)`
    method) — calls `parent.set_status(text)`.
  - `level` is `"info" | "warn" | "error"`. Info: no highlight. Warn:
    amber text. Error: red text. Reverts to default after 5 s via
    `QTimer.singleShot`.
  - Color constants match spec: warn `#D4A017`, error `#DA3633`.
  - No Qt import at module top beyond `QTimer` and `Qt`. No exceptions
    raised from this module.
- **Verify:** `python -m py_compile src/erterface/errors.py` exits 0.
  Manual: call from a smoke harness (or just trust the compile).
- **Risk:** None significant. Standalone helper.

### T2. Rewrite `widgets/card.py` as `QFrame`

- **File:** `src/erterface/widgets/card.py` (rewrite)
- **Acceptance:**
  - `CardWidget` subclasses `QFrame`, **not** `QPushButton`.
  - Signature:
    ```python
    CardWidget(
        title, data_object,
        on_body_click,   # body tap (replaces old on_click)
        on_edit, on_delete, on_move_left, on_move_right,
        on_scan,         # Tree only; pass None for others
        is_dark_mode, reorder_enabled,
    )
    ```
  - Internal layout: body region (custom `QWidget` with
    `mousePressEvent` that emits a new `body_clicked` signal) + action row
    (`QHBoxLayout` of real `QPushButton` children).
  - Body paint: same as v1 generic body / measurement body (thumbnail +
    date/time/pill/ratio for Measurement; title row otherwise).
  - **Pill:** pass `is_dark_mode` to `theme.status_pill_style` (v1
    ignores the flag at `card.py:145`).
  - Action row: `◀` if reorder, `Scan` if Tree, `Edit`, `Delete`, `▶`
    if reorder. Each button has its own `clicked` handler; clicks do not
    bubble to body.
  - 230x160, 8 px corner radius.
  - No `setStyleSheet` rules that target `CardWidget { }` (selector
    changed to `QFrame#cardWidget` via `setObjectName("cardWidget")`).
- **Verify:**
  - `python -m py_compile src/erterface/widgets/card.py` exits 0.
  - Manual: load app, open Plantation with one Zone, one Tree, one
    Measurement (via scan). Confirm:
    - All 4-5 action buttons render fully (no clipped "Delete" / "Scan").
    - Tapping the body drills in; tapping `Scan` pushes scan view;
      tapping `Delete` opens confirm.
- **Risk:** `mousePressEvent` on the body widget must not block children.
  QFrame default ignores; we override on inner body widget only, not on
  CardWidget itself. Children consume events before parent by default.
  Mitigated by smoke test.
- **Files:** 1 (this file).

### T3. Rewrite `dialogs.py`: cut Measurement, add validation

- **File:** `src/erterface/dialogs.py` (rewrite)
- **Acceptance:**
  - `AddEntityDialog` handles **Plantation, Zone, Tree only**. No
    Measurement branch.
  - `make_entity()`: no Measurement branch. Returns `None` for
    `"Measurement"` (defensive — should never be called).
  - New `_validate()` method returns `(ok: bool, message: str)`.
  - Rules per spec table:
    - Plantation: name + id required, name non-empty after strip,
      id unique among all Plantations in `existing_items`.
    - Zone: id required, id matches `[A-Za-z0-9_\-]{1,32}`, id unique
      in same parent.
    - Tree: id required, id matches `[A-Za-z0-9_\-]{1,32}`, id unique
      in same parent.
    - Edit mode: exclude current entity's own id from dup check.
  - `accept()` overridden:
    ```python
    def accept(self):
        ok, msg = self._validate()
        if not ok:
            self._error_label.setText(msg)
            return
        super().accept()
    ```
  - Inline `QLabel` (`objectName="dialogError"`) below form, red text
    `#DA3633`, font 14 px, initially empty.
  - Required field labels append ` *` (e.g. `"Name: *"`).
  - Dialog result codes unchanged: callers still use
    `in (QDialog.DialogCode.Accepted, 2)`.
- **Verify:**
  - `python -m py_compile src/erterface/dialogs.py` exits 0.
  - Manual: try to save a Plantation with empty name → dialog stays
    open, error shows "Name is required." Try empty id → "ID is
    required." Try duplicate id (same parent) → "ID already exists
    in this scope." Valid save closes dialog and creates entity.
- **Risk:** Existing call sites assume no validation. They only
  re-check `exec()` result, which is fine — invalid input returns
  Rejected. No call-site change needed beyond removing Measurement
  in `app.py:edit_entity`.
- **Files:** 1 (this file).

### T4. Refactor `app.py`: top bar, error routing, close path, drop M-CRUD

- **File:** `src/erterface/app.py` (modify)
- **Acceptance:**
  - **Top bar:**
    - `update_time_label()`: write `QDateTime.currentDateTime().toString("HH:mm")` (no "Time:" prefix, no seconds, no date).
    - `lbl_storage` text: drop "Storage:" prefix → `"25 GB free (87%)"`.
    - 4 buttons + 2 short labels + 1 stretch status all fit at 800 px
      with the system default font (manual check at 800x480).
  - **Error routing:**
    - `save_data()`: on exception, call `status_toast(self, "Save
      failed: <reason>", "error")`. Do **not** raise. Do **not** show
      modal.
    - `load_data()`: keep `QMessageBox.warning` (one-time at startup;
      allowed by spec). On reset, also `self.navigation_path.clear()`.
    - `export_csv()`: on exception, `status_toast(self, "Export
      failed: <reason>", "error")`. Remove `QMessageBox.warning`.
    - `_auto_export_csv()`: returns `(path, rows)` on success,
      `None` on failure. On failure, `closeEvent` reports via
      `status_toast`.
    - `sync_drive()`: on `FileNotFoundError` (missing client
      secret), keep `QMessageBox.warning` (allowed: setup hint).
      On other exceptions, `status_toast(self, "Sync failed: ...",
      "error")`. Remove `QMessageBox.information` summary; replace
      with `status_toast(f"Sync done. Up {u} / fail {f} / skip
      {s}.")`.
    - `closeEvent`: save → auto-export → auto-sync. Each step's
      outcome routes to `status_toast`. Bare `except Exception: pass`
      removed. Each step guarded by its own try/except with
      `status_toast` and continue.
  - **Measurement CRUD removed:**
    - `edit_entity()`: no `isinstance(obj, Measurement)` branch.
      That branch's existence was dead-ish but still possible via
      "tap measurement card → details" — actually the tap route is
      `card_clicked` which goes to a read-only `QMessageBox`, not
      `edit_entity`. So `edit_entity` only ever sees
      Plantation/Zone/Tree. Remove the Measurement branch anyway
      (defense in depth).
    - `add_new_entity()`: only Plantation/Zone/Tree reachable. No
      change needed to call site; dialog no longer accepts
      "Measurement".
  - **Card click:** Measurement path still uses `QMessageBox` with
    formatted text (read-only details). Keep.
  - **Add new entity `level == "Plantation"`:** `existing_items` is
    `self.database` (list of Plantations). Validation dedups by
    `plant_id`. Works.
  - **Imports:** add `from .errors import status_toast`. Remove
    unused `QMessageBox` imports if no longer needed (keep: used
    in `delete_entity`, `close_app_safe`, `load_data` warning,
    Measurement details).
- **Verify:**
  - `python -m py_compile src/erterface/app.py` exits 0.
  - Manual:
    - Window 800x480: all 4 top-bar buttons visible, no scroll.
    - Trigger save failure (e.g. chmod plantation_data.json to 000,
      then add entity): status label shows red "Save failed: ..."
      for 5 s. No crash.
    - Add Plantation with empty name: dialog blocks, inline error
      shows.
    - Close app: status label shows save/export/sync results
      sequentially.
- **Risk:** Removing `QMessageBox.information` from sync changes
  user feedback shape. Spec accepts this (status_toast is
  authoritative). Manual smoke verifies.
- **Files:** 1 (this file).

### T5. Cleanup `scan_view.py`: dead code, safer disconnect

- **File:** `src/erterface/scan_view.py` (modify)
- **Acceptance:**
  - Remove lines 182-185: `ts_now` placeholder + `from PyQt6.QtCore
    import QDateTime` mid-function. Move `QDateTime` to top imports
    if needed (it is — already imported indirectly; add to top).
  - `_on_scan_complete`: replace
    `self.btn_run.clicked.disconnect()` (line 198, disconnects
    **all** slots) with a specific disconnect:
    `self.btn_run.clicked.disconnect(self._start_scan)`. This
    prevents accidentally disconnecting anything else connected
    later.
  - `_on_scan_error`: keep the `QMessageBox.warning` (spec allows
    for `scan_error`).
  - All paths produce a `Measurement` only via `_on_done_clicked`,
    never on error.
- **Verify:**
  - `python -m py_compile src/erterface/scan_view.py` exits 0.
  - Manual: trigger scan → completes → Done button shows → click
    Done → new measurement card appears. Trigger scan → cancel
    mid-run → no measurement appears.
- **Risk:** Disconnect API is per-signal per-slot. Specific
  disconnect is the correct pattern.
- **Files:** 1 (this file).

### T6. Fix `theme.py`: `status_pill_style` honors dark mode

- **File:** `src/erterface/theme.py` (modify)
- **Acceptance:**
  - `status_pill_style(classification, is_dark_mode)` currently
    hardcodes `border-radius: 8px;` and ignores `is_dark_mode`. Fix:
    the pill itself doesn't need a dark variant (it's solid color),
    but the font fallback in `font-family: '{LABEL_FONT}',
    sans-serif` is fine. **No functional change needed** to the
    function itself.
  - The bug is at the call site (`card.py:145` passes `False`
    always). T2 fixes the call site. T6 is a no-op audit.
  - **Net action:** T6 may be a no-op. Decide based on T2's
    call-site change. If T2 calls `status_pill_style(classification,
    is_dark_mode)` correctly, T6 is unnecessary. **Mark T6 as
    "skip if T2 covers it."**
- **Verify:** T2 manual check (pill renders correctly in both
  light and dark themes).
- **Files:** 0-1 (T6 likely collapsed into T2).

### T7. `py_compile` gate

- **Files:** none (command)
- **Acceptance:** `python -m py_compile $(git ls-files '*.py')`
  exits 0.
- **Verify:** run the command; expect no output and exit code 0.
- **Risk:** A miss means an import cycle or syntax error. Address
  before T8.

### T8. Manual smoke walkthrough

- **Files:** none
- **Acceptance:** all 17 items in the SPEC.md "Testing strategy"
  checklist pass. Documented as a comment in PR / commit message
  (not in code).
- **Verify:** human walks the checklist on a desktop with PyQt6
  installed. Touch items 4-7 (validation), 11 (scan → measurement),
  15 (Drive local mode), 17 (py_compile) are the high-risk ones.

## Risks summary

| ID | Risk | Mitigation |
| --- | --- | --- |
| R1 | QFrame child button event capture | Body uses inner QWidget override; QFrame default ignores; children consume first. Smoke test. |
| R2 | Dialog accept() override breaks result codes | `super().accept()` only on success; else `return` early. Standard pattern. |
| R3 | status_toast parent doesn't have set_status | `CardApp` already has `set_status()`. Defensive `getattr` fallback in `status_toast`. |
| R4 | Top bar widths depend on font | Smoke test at 800 px. If still overflow, drop status label content. |
| R5 | Threading — save_data runs on UI thread (always) | No change. No QThread in save path. |

## Files touched (summary)

- New: `src/erterface/errors.py`
- Rewrite: `src/erterface/widgets/card.py`
- Rewrite: `src/erterface/dialogs.py`
- Modify: `src/erterface/app.py`
- Modify: `src/erterface/scan_view.py`
- Audit: `src/erterface/theme.py` (likely no-op)
- Unchanged: `models.py`, `paths.py`, `export.py`, `drive_sync.py`,
  `workers.py`, `widgets/keyboard.py`, `widgets/plot.py`

7 files max, 1 file per task. Within the ≤5 files/task rule.

## Reviewable

- Read each task's "Acceptance" — that's the contract.
- Push back on any acceptance bullet before I start implementation.
- Tasks are independent enough to reorder (T2/T3/T6 parallel; T4 after).
