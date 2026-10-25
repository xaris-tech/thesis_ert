"""Single error-render path. Routes user-visible failures to the top-bar
status label. See SPEC.md (Error handling).
"""

from PyQt6.QtCore import QTimer

from . import theme


LEVEL_COLORS = {
    "info": None,
    "warn": theme.STATUS_AT_RISK,
    "error": theme.STATUS_UNHEALTHY,
}

TOAST_DURATION_MS = 5000

DEFAULT_STATUS_STYLE = "font-size: 12px; color: #888888;"
TOAST_INFO_STYLE = "font-size: 12px; color: #888888;"
TOAST_WARN_STYLE = (
    f"font-size: 12px; color: {theme.STATUS_AT_RISK}; font-weight: bold;"
)
TOAST_ERROR_STYLE = (
    f"font-size: 12px; color: {theme.STATUS_UNHEALTHY}; font-weight: bold;"
)


def status_toast(parent, text, level="info"):
    """Write `text` to parent.lbl_status with level-driven color.
    Auto-reverts to default color after TOAST_DURATION_MS. Text persists.
    Overlapping toasts: latest wins (previous timer cancelled).
    """
    setter = getattr(parent, "set_status", None)
    if not callable(setter):
        return
    setter(text)
    label = getattr(parent, "lbl_status", None)
    if label is None:
        return
    _apply_level(label, level)

    prev = getattr(label, "_toast_timer", None)
    if prev is not None:
        prev.stop()
    timer = QTimer(label)
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: _apply_level(label, "info"))
    timer.start(TOAST_DURATION_MS)
    label._toast_timer = timer


def _apply_level(label, level):
    if level == "warn":
        label.setStyleSheet(TOAST_WARN_STYLE)
    elif level == "error":
        label.setStyleSheet(TOAST_ERROR_STYLE)
    else:
        label.setStyleSheet(TOAST_INFO_STYLE)
