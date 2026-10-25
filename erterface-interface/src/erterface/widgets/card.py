"""CardWidget — QFrame with clickable body region and a row of action
buttons (real QPushButtons). Replaces v1's nested-QPushButton design
which had event-capture issues and overflowed the card on Tree cards.

Layout:
    CardWidget(QFrame, CARD_W x CARD_H)
    ├── body region (_CardBody) — title OR thumbnail+meta; emits
    │   body_clicked on left press. Children labels are mouse-transparent
    │   so events always reach the body.
    └── action row (QHBoxLayout) — real QPushButtons, TOUCH_MIN tall:
          ◀ (reorder only)  Edit (not Measurement)  Del  ▶ (reorder only)

Styling comes from card_stylesheet(), set once on the grid container and
keyed by object name; the grid is rebuilt on every navigation, sort and
(debounced) search, so cards carry no stylesheet of their own.
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QPixmapCache
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..models import Measurement
from ..paths import resolve_data_file

CARD_W = 230
CARD_H = 172
THUMB = 84


def _thumbnail(path):
    """84 px thumbnail, cached by path + mtime so a rebuild never re-decodes
    the full-size PNG."""
    try:
        key = f"thumb:{path}:{os.path.getmtime(path)}"
    except OSError:
        return None
    pix = QPixmapCache.find(key)
    if pix is None:
        src = QPixmap(path)
        if src.isNull():
            return None
        pix = src.scaled(
            THUMB, THUMB,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        QPixmapCache.insert(key, pix)
    return pix


def _label(text, name):
    lbl = QLabel(text)
    lbl.setObjectName(name)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    return lbl


def _count(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _summary(obj):
    """One line under a card title, so a tree's state is readable from the grid."""
    if hasattr(obj, "zones"):
        return _count(len(obj.zones), "zone")
    if hasattr(obj, "trees"):
        return _count(len(obj.trees), "tree")
    if hasattr(obj, "measurements"):
        if not obj.measurements:
            return "No scans yet"
        last = max(obj.measurements, key=lambda m: m.timestamp.toMSecsSinceEpoch())
        return f"{_count(len(obj.measurements), 'scan')} · last {last.timestamp.toString('MM-dd')}"
    return ""


class _CardBody(QWidget):
    """Mouse-aware region of the card. Emits body_clicked on left press."""

    body_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.body_clicked.emit()
        super().mousePressEvent(event)


def card_stylesheet(is_dark_mode):
    """Stylesheet for every card in the grid, set once on the grid container.
    Per-card stylesheets made Qt parse and polish one copy per card."""
    c = theme.palette(is_dark_mode)
    button = (
        f"font-size: 14px; font-weight: 700; border-radius: 8px; "
        f"min-height: {theme.TOUCH_MIN}px; max-height: {theme.TOUCH_MIN}px; padding: 0 8px;"
    )
    return (
        f"#cardWidget {{ background-color: {c['surface']}; border: 1px solid {c['border']}; "
        f"border-radius: 12px; }}"
        f"#cardWidget[measurement=\"true\"] {{ background-color: {c['surface_alt']}; }}"
        f"#cardWidget QLabel {{ background: transparent; border: none; color: {c['text']}; }}"
        f"QLabel#title {{ font-size: 18px; font-weight: 800; }}"
        f"QLabel#sub {{ font-size: 12px; color: {c['sub']}; }}"
        f"QLabel#date {{ font-size: 16px; font-weight: 800; }}"
        f"QLabel#time {{ font-size: 13px; color: {c['sub']}; }}"
        f"QLabel#meta {{ font-size: 12px; color: {c['sub']}; }}"
        f"QLabel#thumb {{ border: 1px solid {c['border']}; border-radius: 6px; "
        f"color: {c['sub']}; font-size: 11px; }}"
        f"QFrame#divider {{ background-color: {c['divider']}; border: none; }}"
        f"QPushButton#edit, QPushButton#arrow {{ {button} background-color: {c['neutral']}; "
        f"color: {c['neutral_text']}; border: 1px solid {c['border']}; }}"
        f"QPushButton#arrow {{ min-width: 40px; max-width: 40px; padding: 0; font-size: 16px; }}"
        f"QPushButton#edit:pressed, QPushButton#arrow:pressed {{ background-color: {c['pressed']}; }}"
        f"QPushButton#del {{ {button} background-color: {c['danger_bg']}; "
        f"color: {c['danger_text']}; border: 1px solid {c['danger_border']}; }}"
        f"QPushButton#del:pressed {{ background-color: {c['danger_border']}; }}"
    )


class CardWidget(QFrame):
    def __init__(
        self,
        title,
        data_object,
        on_body_click,
        on_edit,
        on_delete,
        on_move_left,
        on_move_right,
        on_scan,
        is_dark_mode,
        reorder_enabled,
    ):
        super().__init__()
        self.data_object = data_object
        self.setObjectName("cardWidget")
        self.setFixedSize(CARD_W, CARD_H)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        is_measurement = isinstance(data_object, Measurement)
        self.setProperty("measurement", is_measurement)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.body = _CardBody(self)
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(12, 10, 12, 8)
        body_layout.setSpacing(4)
        if is_measurement:
            self._build_measurement_body(body_layout, data_object, is_dark_mode)
        else:
            self._build_generic_body(body_layout, title)
        self.body.body_clicked.connect(lambda: on_body_click(data_object))
        outer.addWidget(self.body, stretch=1)

        divider = QFrame(self)
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        outer.addWidget(divider)

        actions = QHBoxLayout()
        actions.setContentsMargins(8, 6, 8, 8)
        actions.setSpacing(6)
        if reorder_enabled:
            actions.addWidget(self._button("◀", "arrow", lambda: on_move_left(data_object)))
        if not is_measurement:
            actions.addWidget(self._button("Edit", "edit", lambda: on_edit(data_object)), stretch=1)
        actions.addWidget(self._button("Delete", "del", lambda: on_delete(data_object)), stretch=1)
        if reorder_enabled:
            actions.addWidget(self._button("▶", "arrow", lambda: on_move_right(data_object)))
        outer.addLayout(actions)

    @staticmethod
    def _button(text, name, slot):
        btn = QPushButton(text)
        btn.setObjectName(name)
        btn.clicked.connect(slot)
        return btn

    def _build_measurement_body(self, layout, m, is_dark_mode):
        info = QHBoxLayout()
        info.setSpacing(10)

        image_path = resolve_data_file(m.image_path)
        pix = _thumbnail(image_path) if image_path else None
        thumb = _label("" if pix else "No\nimage", "thumb")
        thumb.setFixedSize(THUMB, THUMB)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if pix:
            thumb.setPixmap(pix)
        info.addWidget(thumb)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.setContentsMargins(0, 0, 0, 0)
        text.addWidget(_label(m.timestamp.toString("yyyy-MM-dd"), "date"))
        text.addWidget(_label(m.timestamp.toString("HH:mm"), "time"))
        pill = _label(m.classification, "pill")
        pill.setStyleSheet(theme.status_pill_style(m.classification, is_dark_mode))
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setFixedHeight(24)
        text.addWidget(pill)
        text.addWidget(_label(
            f"Ratio {m.imp_ratio:.3f}" if m.imp_ratio is not None else "Capture run", "meta"
        ))
        text.addStretch()
        info.addLayout(text, stretch=1)
        layout.addLayout(info, stretch=1)

    def _build_generic_body(self, layout, title):
        title_lbl = _label(title, "title")
        title_lbl.setWordWrap(True)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl, stretch=1)
        sub = _label(_summary(self.data_object), "sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)
