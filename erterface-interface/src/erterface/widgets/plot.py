"""Matplotlib canvas for tomogram rendering. Background flips by theme."""

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from .. import theme


class TomogramPlot(FigureCanvas):
    def __init__(self, is_dark_mode=False, parent=None):
        self.figure = Figure(figsize=(3, 3), dpi=80)
        self.axes = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0, right=1, top=1, bottom=0)
        super().__init__(self.figure)
        self.is_dark_mode = is_dark_mode
        self.apply_background_color()
        self.setParent(parent)

    def apply_background_color(self):
        bg = theme.TOMOGRAM_BG_DARK if self.is_dark_mode else theme.TOMOGRAM_BG_LIGHT
        self.figure.patch.set_facecolor(bg)
        self.axes.patch.set_facecolor(bg)

    def plot_data(self, data):
        self.axes.clear()
        self.axes.set_axis_off()
        self.apply_background_color()
        if data is not None:
            self.axes.imshow(data, cmap="RdYlBu_r", interpolation="bicubic", vmin=0, vmax=2.5)
        self.draw_idle()
