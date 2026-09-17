"""Visual theme for the Qt front-end: one palette, one stylesheet, no inline colours.

A light palette. The instrument is used in a lit lab beside a water tank and,
later, outdoors at a tree, where a dark UI on a small Raspberry Pi display is
the wrong choice -- reflections win against a dark ground and lose against a
bright one.

Colours are semantic, not decorative. ``OK`` / ``WARN`` / ``BAD`` map to states
the instrument already defines -- a firmware quality flag, a median resistance
inside or outside the titration window of ADR-0022, a polarity sequence that has
stopped interleaving. Nothing here introduces a new threshold; it only renders
the ones that exist. Keep it that way: a colour that means something the code
cannot compute is a colour that lies.

Status colours are darkened well past their "pretty" value so they hold contrast
against a white card. On an instrument, legible beats vivid.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPixmap, QPolygonF

# -- palette -------------------------------------------------------------

BG = "#eef1f6"
"""Window ground. Faintly cool so white cards read as raised against it."""

SURFACE = "#ffffff"
"""Cards and panels."""

SURFACE_RAISED = "#ffffff"
"""Inputs. Same white as the card, separated by a border rather than a tint."""

SURFACE_SUNKEN = "#f6f8fb"
"""Table header, alternating rows, log console."""

BORDER = "#dbe1ea"
BORDER_STRONG = "#b4bfcd"

TEXT = "#1b2430"
TEXT_MUTED = "#5a6a7e"
TEXT_DIM = "#9aa6b6"

ACCENT = "#1f6feb"
"""Primary action and focus ring."""

ACCENT_HOVER = "#3b84f2"
ACCENT_PRESSED = "#1757c0"

OK = "#0e7a45"
WARN = "#9a5a00"
BAD = "#bd2f2a"
INFO = "#5b46c9"

OK_BG = "#e4f6ec"
WARN_BG = "#fdf2de"
BAD_BG = "#fdeceb"

OK_BORDER = "#8fd3ae"
WARN_BORDER = "#e8bf7e"
BAD_BORDER = "#f0a6a2"

MONO_FAMILY = "Consolas, 'DejaVu Sans Mono', 'Liberation Mono', monospace"
"""Windows first, then what a Raspberry Pi actually ships."""

UI_FAMILY = "'Segoe UI', 'Inter', 'DejaVu Sans', sans-serif"


def qcolor(value: str) -> QColor:
    return QColor(value)


# Table row tints. The flagged background is kept pale so the red text on top of
# it stays the thing that carries, rather than competing with its own fill.
ROW_FLAGGED_BG = qcolor(BAD_BG)
ROW_FLAGGED_FG = qcolor(BAD)
ROW_OK_FG = qcolor(TEXT)
ROW_MUTED_FG = qcolor(TEXT_MUTED)


# -- arrow icons ---------------------------------------------------------
#
# Combo and spin arrows are painted to PNG at runtime rather than described in
# CSS. Qt's stylesheet engine takes over drawing a sub-control entirely once any
# rule touches it, and it has no way to render a border-triangle: the arrow
# comes out as a filled rectangle regardless of a zero width/height. Shipping
# binary assets for four triangles is worse than drawing them, and drawing them
# keeps the colour tied to the palette above instead of baked into a file.

ARROW_WIDTH = 9
ARROW_HEIGHT = 6

_arrow_cache: dict[tuple[str, str], str] = {}


def _arrow_dir() -> Path:
    path = Path(tempfile.gettempdir()) / "tree-ert-qt-icons"
    path.mkdir(parents=True, exist_ok=True)
    return path


def arrow_icon(direction: str, color: str) -> str:
    """Path to a triangle PNG, as a forward-slashed string for QSS ``url()``.

    Requires a live QApplication, so it is called when the stylesheet is built
    rather than at import time. Results are cached per (direction, colour): the
    four icons are identical for every widget that uses them.
    """
    key = (direction, color)
    cached = _arrow_cache.get(key)
    if cached and Path(cached).exists():
        return cached

    scale = 4  # drawn oversized and smoothed down, so the edges are not ragged
    pixmap = QPixmap(ARROW_WIDTH * scale, ARROW_HEIGHT * scale)
    pixmap.fill(QColor(0, 0, 0, 0))

    width = ARROW_WIDTH * scale
    height = ARROW_HEIGHT * scale
    if direction == "down":
        points = [QPointF(0, 0), QPointF(width, 0), QPointF(width / 2, height)]
    else:
        points = [QPointF(0, height), QPointF(width, height), QPointF(width / 2, 0)]

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(color)))
    painter.drawPolygon(QPolygonF(points))
    painter.end()

    scaled = pixmap.scaled(
        ARROW_WIDTH,
        ARROW_HEIGHT,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    path = _arrow_dir() / f"arrow-{direction}-{color.lstrip('#')}.png"
    scaled.save(str(path), "PNG")
    resolved = str(path).replace("\\", "/")
    _arrow_cache[key] = resolved
    return resolved


def stylesheet() -> str:
    """The stylesheet with arrow icon paths resolved. Needs a QApplication."""
    return (
        STYLESHEET.replace("__ARROW_DOWN__", arrow_icon("down", TEXT_MUTED))
        .replace("__ARROW_UP__", arrow_icon("up", TEXT_MUTED))
        .replace("__ARROW_DOWN_DIM__", arrow_icon("down", TEXT_DIM))
        .replace("__ARROW_UP_DIM__", arrow_icon("up", TEXT_DIM))
    )


STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: {UI_FAMILY};
    font-size: 10pt;
}}

QMainWindow, QSplitter, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: {BG};
}}

QSplitter::handle {{
    background: {BORDER};
    width: 1px;
}}

/* -- header ---------------------------------------------------------- */

#HeaderBar {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}

#HeaderTitle {{
    font-size: 15pt;
    font-weight: 600;
    color: {TEXT};
}}

#HeaderSubtitle {{
    font-size: 9pt;
    color: {TEXT_MUTED};
}}

/* -- cards ----------------------------------------------------------- */

QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 14px 14px 14px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background: {SURFACE};
    color: {TEXT_MUTED};
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 1px;
}}

QLabel {{
    background: transparent;
    color: {TEXT};
}}

#SectionLabel {{
    color: {TEXT_MUTED};
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 1px;
    padding-top: 4px;
}}

/* -- inputs ---------------------------------------------------------- */

QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {SURFACE_RAISED};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 6px 8px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    min-height: 22px;
}}

QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border-color: {TEXT_DIM};
}}

QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled {{
    color: {TEXT_DIM};
    background: {SURFACE_SUNKEN};
    border-color: {BORDER};
}}

/* Combo box. The arrow is a pure-CSS triangle, which requires an element of
   zero size: without width/height 0 Qt gives the sub-control its default box
   and paints the borders around it, which renders as a small filled square. */

QComboBox::drop-down {{
    subcontrol-origin: border;
    subcontrol-position: center right;
    width: 24px;
    border: none;
    background: transparent;
}}

QComboBox::down-arrow {{
    image: url(__ARROW_DOWN__);
    width: {ARROW_WIDTH}px;
    height: {ARROW_HEIGHT}px;
    margin-right: 8px;
}}

QComboBox::down-arrow:disabled {{
    image: url(__ARROW_DOWN_DIM__);
}}

QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    outline: none;
    padding: 4px;
}}

/* Spin boxes. Same zero-size rule for the arrows; the buttons are pinned to the
   right edge so they cannot stack into one tall blob. */

QSpinBox, QDoubleSpinBox {{
    padding-right: 20px;
}}

/* Button heights are fixed rather than a percentage: Qt does not resolve a
   percentage height for a spin-box sub-control, and the two buttons then
   overlap into one, which renders as a single arrow. 17 + 17 matches the
   36px field height set by min-height plus vertical padding. */

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 19px;
    height: 17px;
    border: none;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 5px;
    background: {SURFACE_SUNKEN};
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 19px;
    height: 17px;
    border: none;
    border-left: 1px solid {BORDER};
    border-top: 1px solid {BORDER};
    border-bottom-right-radius: 5px;
    background: {SURFACE_SUNKEN};
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {BORDER};
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url(__ARROW_UP__);
    width: {ARROW_WIDTH}px;
    height: {ARROW_HEIGHT}px;
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url(__ARROW_DOWN__);
    width: {ARROW_WIDTH}px;
    height: {ARROW_HEIGHT}px;
}}

QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled,
QSpinBox::up-arrow:off, QDoubleSpinBox::up-arrow:off {{
    image: url(__ARROW_UP_DIM__);
}}

QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled,
QSpinBox::down-arrow:off, QDoubleSpinBox::down-arrow:off {{
    image: url(__ARROW_DOWN_DIM__);
}}

QCheckBox {{
    background: transparent;
    spacing: 8px;
    padding: 2px 0;
}}

QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 4px;
    border: 1px solid {BORDER_STRONG};
    background: {SURFACE_RAISED};
}}

QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}

QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
}}

/* -- buttons --------------------------------------------------------- */

QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 8px 14px;
    color: {TEXT};
    font-weight: 600;
    min-height: 24px;
}}

QPushButton:hover {{
    background: {SURFACE_SUNKEN};
    border-color: {TEXT_DIM};
}}

QPushButton:pressed {{
    background: {BORDER};
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    background: {SURFACE_SUNKEN};
    border-color: {BORDER};
}}

QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #ffffff;
    padding: 9px 16px;
}}

QPushButton#Primary:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QPushButton#Primary:pressed {{
    background: {ACCENT_PRESSED};
}}

QPushButton#Primary:disabled {{
    background: {SURFACE_SUNKEN};
    border-color: {BORDER};
    color: {TEXT_DIM};
}}

QPushButton#Danger {{
    background: {SURFACE};
    border: 1px solid {BAD_BORDER};
    color: {BAD};
    padding: 9px 16px;
}}

QPushButton#Danger:hover {{
    background: {BAD_BG};
    border-color: {BAD};
}}

QPushButton#Danger:disabled {{
    border-color: {BORDER};
    color: {TEXT_DIM};
    background: {SURFACE_SUNKEN};
}}

QPushButton#Subtle {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {TEXT_MUTED};
    font-weight: 500;
    padding: 6px 10px;
    min-height: 20px;
}}

QPushButton#Subtle:hover {{
    background: {SURFACE_SUNKEN};
    color: {TEXT};
    border-color: {BORDER_STRONG};
}}

QPushButton#Subtle:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
    background: transparent;
}}

/* Icon-sized button sitting next to a field it acts on. */
QPushButton#Inline {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    color: {TEXT_MUTED};
    font-weight: 600;
    padding: 6px 10px;
    min-height: 24px;
    max-width: 34px;
}}

QPushButton#Inline:hover {{
    background: {SURFACE_SUNKEN};
    color: {ACCENT};
    border-color: {ACCENT};
}}

/* -- status readouts -------------------------------------------------- */

#StatusPill {{
    font-family: {MONO_FAMILY};
    font-size: 10pt;
    border-radius: 6px;
    padding: 9px 12px;
    border: 1px solid {BORDER};
    background: {SURFACE};
    color: {TEXT_MUTED};
}}

#StatusPill[state="ok"] {{
    background: {OK_BG};
    border-color: {OK_BORDER};
    color: {OK};
}}

#StatusPill[state="warn"] {{
    background: {WARN_BG};
    border-color: {WARN_BORDER};
    color: {WARN};
}}

#StatusPill[state="bad"] {{
    background: {BAD_BG};
    border-color: {BAD_BORDER};
    color: {BAD};
}}

#StatusPill[state="busy"] {{
    background: #e8f1fe;
    border-color: {ACCENT};
    color: {ACCENT_PRESSED};
}}

#SessionPanel {{
    font-family: {MONO_FAMILY};
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-left: 3px solid {INFO};
    border-radius: 6px;
    padding: 10px 12px;
    color: {TEXT};
}}

/* -- table ----------------------------------------------------------- */

QTableWidget {{
    background: {SURFACE};
    alternate-background-color: {SURFACE_SUNKEN};
    border: 1px solid {BORDER};
    border-radius: 6px;
    gridline-color: {BORDER};
    font-family: {MONO_FAMILY};
    font-size: 9pt;
    selection-background-color: #dbe8fb;
    selection-color: {TEXT};
}}

QHeaderView {{
    background: {SURFACE_SUNKEN};
}}

QHeaderView::section {{
    background: {SURFACE_SUNKEN};
    color: {TEXT_MUTED};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 7px 4px;
    font-weight: 700;
    font-size: 8pt;
}}

QHeaderView::section:last {{
    border-right: none;
}}

QTableCornerButton::section {{
    background: {SURFACE_SUNKEN};
    border: none;
}}

#ImageCanvas {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    color: {TEXT_MUTED};
    padding: 8px;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    background: {SURFACE};
    top: -1px;
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    border: 1px solid transparent;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 7px 16px;
    margin-right: 2px;
    font-weight: 600;
    font-size: 9pt;
}}

QTabBar::tab:selected {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-bottom-color: {SURFACE};
}}

QTabBar::tab:hover:!selected {{
    color: {TEXT};
}}

/* -- log console ------------------------------------------------------ */

#LogConsole {{
    background: {SURFACE_SUNKEN};
    border: 1px solid {BORDER};
    border-radius: 6px;
    font-family: {MONO_FAMILY};
    font-size: 9pt;
    color: {TEXT_MUTED};
    padding: 8px;
}}

/* -- scrollbars ------------------------------------------------------- */

QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_DIM};
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* -- dialogs ---------------------------------------------------------- */

QMessageBox {{
    background: {SURFACE};
}}

QMessageBox QLabel {{
    background: transparent;
}}

QMessageBox QPushButton {{
    min-width: 84px;
}}

QToolTip {{
    background: {TEXT};
    color: #ffffff;
    border: none;
    padding: 5px 8px;
    border-radius: 4px;
}}
"""


def apply_state(widget, state: str | None) -> None:
    """Set a widget's ``state`` property and force Qt to restyle it.

    Qt does not re-evaluate property selectors on its own when a property
    changes, so without the unpolish/polish the stylesheet silently keeps the
    previous colour -- a status pill stuck on green while the frame it describes
    is flagged.
    """
    widget.setProperty("state", state or "")
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def frame_state(summary) -> str:
    """Map a :class:`~tree_ert.capture_view.FrameSummary` to a pill state.

    Only states the instrument already defines. Worst-first: a frame with
    flagged records is bad regardless of where its resistance sits, because the
    resistance was computed from records that include the flagged ones.
    """
    if summary.record_count == 0:
        return ""
    if summary.ok_count < summary.record_count:
        return "bad"
    if not summary.polarity_alternates:
        return "bad"
    if summary.quantisation_limited:
        # Not "bad": the records are valid, they are just at the converter's
        # resolution. The measurement is real but a difference image built on
        # it will be dominated by rounding (ADR-0026).
        return "warn"
    return "ok"
