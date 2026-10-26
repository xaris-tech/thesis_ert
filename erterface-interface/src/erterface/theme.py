"""Color constants, font loading, and theme application. Tokens sourced
from precision_arboreal_system/DESIGN.md. The grayscale constraint is
disregarded per user direction; status colors use
color for semantic clarity.
"""

import os

from PyQt6.QtGui import QFont, QFontDatabase

from . import paths


LIGHT_BG = "#f2f4f7"
DARK_BG = "#121212"

# Pill colours carry white text and are read in direct sunlight, so each
# clears WCAG AA (4.5:1) against #ffffff. The earlier #D4A017 amber was 2.2:1.
STATUS_HEALTHY = "#1a7f37"
STATUS_AT_RISK = "#9a6700"
STATUS_UNHEALTHY = "#c9252d"
STATUS_UNCLASSIFIED = "#57606a"

# Minimum touch target for gloved fingers on the 7" display.
TOUCH_MIN = 44


def palette(is_dark_mode):
    """Surface/text tokens shared by every screen. Light mode is the field
    (sunlight) theme: near-black text and borders dark enough to survive glare."""
    if is_dark_mode:
        return {
            "bg": DARK_BG, "surface": "#1e1e1e", "surface_alt": "#262626",
            "border": "#3d3d3d", "divider": "#2e2e2e",
            "text": "#f5f5f5", "sub": "#b4bfcc",
            "neutral": "#2a2a2a", "neutral_text": "#f5f5f5", "pressed": "#3a3a3a",
            "danger_bg": "#3a1d1d", "danger_text": "#ff9b9b", "danger_border": "#6a2a2a",
            "accent": "#2ea043",
        }
    return {
        "bg": LIGHT_BG, "surface": "#ffffff", "surface_alt": "#f7f9fb",
        "border": "#a9b4c0", "divider": "#dde3ea",
        "text": "#0b1220", "sub": "#3d4b5c",
        "neutral": "#e8edf2", "neutral_text": "#0b1220", "pressed": "#cfd8e3",
        "danger_bg": "#fff1f1", "danger_text": "#a4161a", "danger_border": "#e8a0a0",
        "accent": "#1a7f37",
    }


TOMOGRAM_BG_LIGHT = "#f9f9f9"
TOMOGRAM_BG_DARK = "#1e1e1e"

HEADLINE_FONT = "Hanken Grotesk"
LABEL_FONT = "Geist"

DEFAULT_FONT_POINT_SIZE = 11
HEADLINE_FONT_POINT_SIZE = 13
LABEL_FONT_POINT_SIZE = 11

_loaded_families = []


def status_color(classification):
    return {
        "HEALTHY": STATUS_HEALTHY,
        "AT_RISK": STATUS_AT_RISK,
        "UNHEALTHY": STATUS_UNHEALTHY,
        "UNCLASSIFIED": STATUS_UNCLASSIFIED,
    }.get(classification, STATUS_UNHEALTHY)


def status_pill_style(classification, is_dark_mode):
    color = status_color(classification)
    return (
        f"QLabel {{"
        f"background-color: {color};"
        f"color: #ffffff;"
        f"font-family: '{LABEL_FONT}', sans-serif;"
        f"font-size: 13px;"
        f"font-weight: bold;"
        f"padding: 4px 10px;"
        f"border-radius: 8px;"
        f"}}"
    )


def load_fonts():
    """Try to load fonts from ./assets/fonts/. Returns the list of family
    names actually registered. Falls back to system sans-serif silently.
    """
    global _loaded_families
    _loaded_families = []
    if not os.path.isdir(paths.FONTS_DIR):
        return _loaded_families
    for fname in os.listdir(paths.FONTS_DIR):
        if not fname.lower().endswith((".ttf", ".otf")):
            continue
        fpath = os.path.join(paths.FONTS_DIR, fname)
        font_id = QFontDatabase.addApplicationFont(fpath)
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        _loaded_families.extend(families)
    return _loaded_families


def available_fonts():
    return list(_loaded_families)


def default_font(point_size=None):
    """Application default body font. Uses Hanken Grotesk if loaded,
    else the first available bundled font, else system sans-serif.
    Always returns a QFont with a positive point size.
    """
    size = point_size if point_size is not None else DEFAULT_FONT_POINT_SIZE
    if size is None or size <= 0:
        size = DEFAULT_FONT_POINT_SIZE
    family = HEADLINE_FONT if HEADLINE_FONT in _loaded_families else None
    if family is None and _loaded_families:
        family = _loaded_families[0]
    f = QFont(family if family else "Segoe UI", size)
    f.setStyleHint(QFont.StyleHint.SansSerif)
    if family and family not in QFontDatabase.families():
        f.setFamily("Segoe UI")
    return f


def headline_font(point_size=None, weight=QFont.Weight.Bold):
    size = point_size if point_size is not None else HEADLINE_FONT_POINT_SIZE
    family = HEADLINE_FONT if HEADLINE_FONT in _loaded_families else "Segoe UI"
    f = QFont(family, size)
    f.setWeight(weight)
    return f


def label_font(point_size=None, weight=QFont.Weight.Medium):
    size = point_size if point_size is not None else LABEL_FONT_POINT_SIZE
    family = LABEL_FONT if LABEL_FONT in _loaded_families else "Segoe UI"
    f = QFont(family, size)
    f.setWeight(weight)
    return f


def make_touch_scrollable(viewport):
    """Drag-to-scroll that does not eat taps: the press reaches the card at
    once (Qt's default holds it back) and only an 8 mm drag scrolls, so a
    slightly moving fingertip still taps. Same settings as the capture
    session's tree_ert.qt.theme.make_touch_scrollable."""
    from PyQt6.QtWidgets import QScroller, QScrollerProperties

    QScroller.grabGesture(viewport, QScroller.ScrollerGestureType.LeftMouseButtonGesture)
    scroller = QScroller.scroller(viewport)
    props = scroller.scrollerProperties()
    metric = QScrollerProperties.ScrollMetric
    props.setScrollMetric(metric.MousePressEventDelay, 0.0)
    props.setScrollMetric(metric.DragStartDistance, 0.008)
    off = QScrollerProperties.OvershootPolicy.OvershootAlwaysOff
    props.setScrollMetric(metric.HorizontalOvershootPolicy, off)
    props.setScrollMetric(metric.VerticalOvershootPolicy, off)
    scroller.setScrollerProperties(props)
