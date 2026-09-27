"""The revamp's two charts, drawn with QPainter.

:class:`AxisBarChart` - horizontal bars with a value axis beneath and dashed
vertical grid lines, labels right-aligned on the left, as Recharts draws the
revamp's "SIF exposure by IOGP rule" and "Failed barrier controls".

:class:`TrendChart` - the weekly risk trend: SIF potential (solid navy) and
critical (dashed red) on the left axis, total reports (dotted grey) on the
right, a dashed amber average line, smooth curves with dots, and a bar mode.
Hovering shows the week's figures.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QFontMetrics, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QSizePolicy, QToolTip, QWidget

__all__ = ["AxisBarChart", "RadarChart", "TrendChart", "nice_ticks"]

GRID = "#F0F0F0"
TICK = "#9CA3AF"
LABEL = "#6B7280"


def nice_ticks(top: float, count: int = 5) -> List[float]:
    """Round tick values from 0 up to at least ``top``."""
    if top <= 0:
        return [0, 1]
    raw = top / max(1, count - 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    ticks, value = [], 0.0
    while value < top + step * 0.001:
        ticks.append(round(value, 6))
        value += step
    if ticks[-1] < top:
        ticks.append(round(value, 6))
    return ticks


def _fmt(value: float) -> str:
    return f"{value:g}"


def two_lines(label: str, metrics: QFontMetrics, width: int) -> str:
    """The label in at most two lines, the second elided - rows never overlap."""
    if metrics.horizontalAdvance(label) <= width:
        return label
    words = label.split()
    first = ""
    while words and metrics.horizontalAdvance((first + " " + words[0]).strip()) <= width:
        first = (first + " " + words.pop(0)).strip()
    if not first:  # one long word
        return metrics.elidedText(label, Qt.TextElideMode.ElideRight, width)
    rest = metrics.elidedText(" ".join(words), Qt.TextElideMode.ElideRight, width)
    return f"{first}\n{rest}" if rest else first


class AxisBarChart(QWidget):
    """Horizontal bars over a value axis."""

    def __init__(self, colour: str = "#1E3A5F", *, label_width: int = 120,
                 bar_height: int = 10, row: int = 24) -> None:
        super().__init__()
        self.colour = colour
        self.label_width = label_width
        self.bar_height = bar_height
        self.row = row
        self.items: List[Tuple[str, float]] = []
        self.empty = "Nothing to show yet."
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._resize()

    def set_items(self, items: Sequence[Tuple[str, float]]) -> None:
        self.items = [(str(label), float(value)) for label, value in items]
        self._resize()
        self.update()

    def _resize(self) -> None:
        self.setFixedHeight(max(3, len(self.items)) * self.row + 30)

    def _font(self, size: int) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(size)
        return font

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.items:
            painter.setPen(QColor(TICK))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft, self.empty)
            return
        left = self.label_width + 8
        right = self.width() - 20
        plot = QRectF(left, 0, max(20, right - left), len(self.items) * self.row)
        ticks = nice_ticks(max(value for _label, value in self.items))
        top = ticks[-1] or 1
        painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
        for tick in ticks:
            x = plot.left() + plot.width() * tick / top
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        label_font = self._font(10)
        painter.setFont(label_font)
        metrics = QFontMetrics(label_font)
        for index, (label, value) in enumerate(self.items):
            y = plot.top() + index * self.row
            painter.setPen(QColor(LABEL))
            painter.drawText(QRect(0, int(y), self.label_width, self.row),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                             , two_lines(label, metrics, self.label_width - 2))
            width = plot.width() * value / top
            bar = QRectF(plot.left(), y + (self.row - self.bar_height) / 2,
                         max(2.0, width), self.bar_height)
            path = QPainterPath()
            path.addRoundedRect(bar, 3, 3)
            painter.fillPath(path, QColor(self.colour))
            painter.fillRect(QRectF(bar.left(), bar.top(), min(3.0, bar.width()), bar.height()),
                             QColor(self.colour))
        painter.setPen(QColor(TICK))
        for tick in ticks:
            x = plot.left() + plot.width() * tick / top
            painter.drawText(QRectF(x - 20, plot.bottom() + 6, 40, 14),
                             Qt.AlignmentFlag.AlignHCenter, _fmt(tick))

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        index = int(event.position().y() // self.row)
        if 0 <= index < len(self.items):
            label, value = self.items[index]
            QToolTip.showText(event.globalPosition().toPoint(), f"{label}\nCount: {value:g}", self)
        else:
            QToolTip.hideText()


class TrendChart(QWidget):
    """Weekly SIF potential, critical and total reports."""

    NAVY = "#1E3A5F"
    RED = "#DC2626"
    GREY = "#9CA3AF"
    AMBER = "#FBBF24"

    def __init__(self) -> None:
        super().__init__()
        self.mode = "line"
        self.weeks: List[str] = []
        self.sif: List[float] = []
        self.critical: List[float] = []
        self.reports: List[float] = []
        self.reference: Optional[Tuple[float, str]] = None
        #: Under the x axis: "Week commencing", "Hour of day", "Day", "Month".
        self.axis_caption = "Week commencing"
        #: Curves for weeks and months; straight lines for hourly and daily counts.
        self.smooth = True
        self.hover = -1
        self.setMinimumHeight(240)
        self.setMouseTracking(True)

    def set_data(self, weeks: Sequence[str], sif: Sequence[float], critical: Sequence[float],
                 reports: Sequence[float], reference: Optional[Tuple[float, str]] = None,
                 titles: Sequence[str] = ()) -> None:
        self.weeks, self.sif, self.critical, self.reports = (list(weeks), list(sif),
                                                              list(critical), list(reports))
        #: What each point's tooltip is headed with - the whole week, with its year.
        self.titles = list(titles) or [f"w/c {week}" for week in self.weeks]
        self.reference = reference
        self.update()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update()

    # -- geometry ------------------------------------------------------------------

    def _plot(self) -> QRectF:
        return QRectF(52, 10, max(60, self.width() - 52 - 64), max(60, self.height() - 10 - 40))

    def _x(self, plot: QRectF, index: int) -> float:
        count = max(1, len(self.weeks) - 1)
        return plot.left() + plot.width() * index / count if len(self.weeks) > 1 \
            else plot.center().x()

    @staticmethod
    def _smooth(points: List[QPointF]) -> QPainterPath:
        """A curve through every point with no overshoot between them."""
        path = QPainterPath()
        if not points:
            return path
        path.moveTo(points[0])
        for i in range(1, len(points)):
            p0, p1 = points[i - 1], points[i]
            dx = (p1.x() - p0.x()) / 3
            path.cubicTo(QPointF(p0.x() + dx, p0.y()), QPointF(p1.x() - dx, p1.y()), p1)
        return path

    # -- painting ---------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self._plot()
        small = QFont(self.font())
        small.setPixelSize(10)
        painter.setFont(small)
        if not self.weeks:
            painter.setPen(QColor(TICK))
            painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter,
                             "No dated reports in this period.")
            return
        # Counts: whole-number ticks, never "0.5 incidents".
        left_ticks = nice_ticks(max(max(self.sif + self.critical + [1]) * 1.1, 4), 5)
        right_ticks = nice_ticks(max(max(self.reports + [1]) * 1.1, 4), 5)
        left_top, right_top = left_ticks[-1] or 1, right_ticks[-1] or 1

        def y_left(value: float) -> float:
            return plot.bottom() - plot.height() * value / left_top

        def y_right(value: float) -> float:
            return plot.bottom() - plot.height() * value / right_top

        painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
        for tick in left_ticks:
            painter.drawLine(QPointF(plot.left(), y_left(tick)), QPointF(plot.right(), y_left(tick)))
        painter.setPen(QColor(TICK))
        for tick in left_ticks:
            painter.drawText(QRectF(plot.left() - 36, y_left(tick) - 7, 30, 14),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, _fmt(tick))
        if self.mode == "line":
            for tick in right_ticks:
                painter.drawText(QRectF(plot.right() + 6, y_right(tick) - 7, 30, 14),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                 _fmt(tick))
        # As many labels as fit without touching.
        widest = max(painter.fontMetrics().horizontalAdvance(week) for week in self.weeks) + 14
        step = max(1, math.ceil(len(self.weeks) / max(2, int(plot.width() // widest))))
        last = len(self.weeks) - 1
        for index, week in enumerate(self.weeks):
            # The last label too, unless it would sit on the one before it.
            if index % step == 0 or (index == last and last % step >= max(1, step // 2 + 1)):
                x = self._x(plot, index)
                painter.drawText(QRectF(x - 30, plot.bottom() + 6, 60, 14),
                                 Qt.AlignmentFlag.AlignHCenter, week)
        painter.drawText(QRectF(plot.right() - 150, plot.bottom() + 22, 150, 14),
                         Qt.AlignmentFlag.AlignRight, self.axis_caption)
        painter.save()
        painter.translate(14, plot.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-40, -7, 80, 14), Qt.AlignmentFlag.AlignCenter,
                         "Incidents" if self.mode == "line" else "Count")
        painter.restore()
        if self.mode == "line":
            painter.save()
            painter.translate(self.width() - 10, plot.center().y())
            painter.rotate(90)
            painter.drawText(QRectF(-40, -7, 80, 14), Qt.AlignmentFlag.AlignCenter, "Reports")
            painter.restore()

        if self.mode == "bar":
            self._paint_bars(painter, plot, y_left)
        else:
            self._paint_lines(painter, plot, y_left, y_right)
        if 0 <= self.hover < len(self.weeks):
            x = self._x(plot, self.hover)
            painter.setPen(QPen(QColor("#D1D5DB"), 1))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))

    def _paint_lines(self, painter: QPainter, plot: QRectF, y_left, y_right) -> None:
        if self.reference is not None:
            value, label = self.reference
            y = y_left(value)
            painter.setPen(QPen(QColor(self.AMBER), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor("#D97706"))
            small = QFont(painter.font())
            small.setPixelSize(9)
            painter.setFont(small)
            painter.drawText(QRectF(plot.right() - 70, y - 14, 70, 12),
                             Qt.AlignmentFlag.AlignRight, label)
        series = ((self.reports, self.GREY, 1.0, Qt.PenStyle.DotLine, y_right, False),
                  (self.critical, self.RED, 2.0, Qt.PenStyle.DashLine, y_left, True),
                  (self.sif, self.NAVY, 2.5, Qt.PenStyle.SolidLine, y_left, True))
        for values, colour, width, style, scale, dots in series:
            points = [QPointF(self._x(plot, i), scale(v)) for i, v in enumerate(values)]
            painter.setPen(QPen(QColor(colour), width, style))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if self.smooth:
                painter.drawPath(self._smooth(points))
            else:
                painter.drawPolyline(QPolygonF(points))
            if dots:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(colour))
                for index, point in enumerate(points):
                    radius = 5 if index == self.hover else 3
                    painter.drawEllipse(point, radius, radius)

    def _paint_bars(self, painter: QPainter, plot: QRectF, y_left) -> None:
        slot = plot.width() / max(1, len(self.weeks))
        width = min(12.0, slot / 3)
        for index in range(len(self.weeks)):
            x = self._x(plot, index)
            for offset, values, colour in ((-width, self.sif, self.NAVY), (0, self.critical, self.RED)):
                if values[index] <= 0:
                    continue          # nothing to draw - not a stub that reads as "some"
                top = y_left(values[index])
                bar = QRectF(x + offset, top, width, plot.bottom() - top)
                path = QPainterPath()
                path.addRoundedRect(bar, 3, 3)
                painter.fillPath(path, QColor(colour))
                painter.fillRect(QRectF(bar.left(), bar.bottom() - 3, bar.width(), 3), QColor(colour))

    # -- hover --------------------------------------------------------------------------

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self.weeks:
            return
        plot = self._plot()
        count = max(1, len(self.weeks) - 1)
        index = round((event.position().x() - plot.left()) / plot.width() * count)
        index = max(0, min(len(self.weeks) - 1, index))
        if index != self.hover:
            self.hover = index
            self.update()
        QToolTip.showText(event.globalPosition().toPoint(),
                          f"{self.titles[index]}\nSIF potential: {self.sif[index]:g}\n"
                          f"Critical risk: {self.critical[index]:g}\n"
                          f"Total reports: {self.reports[index]:g}", self)

    def leaveEvent(self, _event) -> None:  # noqa: N802
        self.hover = -1
        self.update()


class RadarChart(QWidget):
    """A spider chart: one spoke per category, one polygon per series.

    Rings at round counts, the category's short name at each spoke's end, and
    the three series the trend draws - all reports (grey), SIF potential
    (navy) and critical (red) - on one scale, so their shapes compare honestly.
    Hovering near a spoke shows its full name and counts.
    """

    SERIES = (("All reports", "#9CA3AF", 40), ("SIF potential", "#1E3A5F", 70),
              ("Critical risk", "#DC2626", 60))

    def __init__(self) -> None:
        super().__init__()
        #: (full name, short label, sif, critical, all) per spoke.
        self.axes: List[Tuple[str, str, int, int, int]] = []
        self.hover = -1
        self.setMinimumSize(300, 300)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_axes(self, axes: Sequence[Tuple[str, str, int, int, int]]) -> None:
        self.axes = list(axes)
        self.hover = -1
        self.update()

    def _geometry(self) -> Tuple[QPointF, float]:
        """The centre, and a radius that leaves room for the longest label beside it."""
        font = QFont(self.font())
        font.setPixelSize(11)
        widest = max([QFontMetrics(font).horizontalAdvance(axis[1]) for axis in self.axes] + [40])
        centre = QPointF(self.width() / 2, self.height() / 2 + 4)
        radius = max(40.0, min(self.width() / 2 - widest - 18, self.height() / 2 - 34))
        return centre, radius

    def _point(self, centre: QPointF, radius: float, index: int, share: float) -> QPointF:
        angle = -math.pi / 2 + 2 * math.pi * index / max(1, len(self.axes))
        return QPointF(centre.x() + radius * share * math.cos(angle),
                       centre.y() + radius * share * math.sin(angle))

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        small = QFont(self.font())
        small.setPixelSize(10)
        painter.setFont(small)
        if len(self.axes) < 3:
            painter.setPen(QColor(TICK))
            painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter,
                             "Not enough categories to draw.")
            return
        centre, radius = self._geometry()
        top = max([axis[4] for axis in self.axes] + [4])
        ticks = [tick for tick in nice_ticks(top, 4) if tick > 0]
        scale = ticks[-1] if ticks else 1
        count = len(self.axes)
        # Rings and spokes.
        painter.setPen(QPen(QColor("#E5E7EB"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for tick in ticks:
            ring = QPainterPath()
            for index in range(count + 1):
                point = self._point(centre, radius, index % count, tick / scale)
                ring.moveTo(point) if index == 0 else ring.lineTo(point)
            painter.drawPath(ring)
        for index in range(count):
            painter.drawLine(centre, self._point(centre, radius, index, 1.0))
        painter.setPen(QColor(TICK))
        for tick in ticks:
            point = self._point(centre, radius, 0, tick / scale)
            painter.drawText(QRectF(point.x() + 4, point.y() + 1, 30, 12),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                             _fmt(tick))
        # Series, largest first so the smaller shapes sit on top.
        for series, (_name, colour, alpha) in zip((4, 2, 3), self.SERIES):
            polygon = QPainterPath()
            points = [self._point(centre, radius, index, axis[series] / scale)
                      for index, axis in enumerate(self.axes)]
            polygon.moveTo(points[0])
            for point in points[1:]:
                polygon.lineTo(point)
            polygon.closeSubpath()
            fill = QColor(colour)
            fill.setAlpha(alpha)
            painter.setBrush(fill)
            painter.setPen(QPen(QColor(colour), 1.8 if series != 4 else 1.0,
                                Qt.PenStyle.DashLine if series == 3 else Qt.PenStyle.SolidLine))
            painter.drawPath(polygon)
            if series != 4:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(colour))
                for index, point in enumerate(points):
                    size = 4.5 if index == self.hover else 2.6
                    painter.drawEllipse(point, size, size)
        # Labels at the spokes' ends.
        label_font = QFont(self.font())
        label_font.setPixelSize(11)
        painter.setFont(label_font)
        metrics = QFontMetrics(label_font)
        for index, axis in enumerate(self.axes):
            point = self._point(centre, radius + 12, index, 1.0)
            text = axis[1]
            width = metrics.horizontalAdvance(text) + 4
            dx = point.x() - centre.x()
            left = point.x() - width / 2 if abs(dx) < 8 else (point.x() if dx > 0
                                                               else point.x() - width)
            box = QRectF(left, point.y() - 8, width, 16)
            painter.setPen(QColor("#10213A" if index == self.hover else LABEL))
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if len(self.axes) < 3:
            return
        centre, radius = self._geometry()
        dx = event.position().x() - centre.x()
        dy = event.position().y() - centre.y()
        if math.hypot(dx, dy) > radius + 40:
            self.leaveEvent(None)
            return
        angle = (math.atan2(dy, dx) + math.pi / 2) % (2 * math.pi)
        index = round(angle / (2 * math.pi) * len(self.axes)) % len(self.axes)
        if index != self.hover:
            self.hover = index
            self.update()
        name, _short, sif, critical, total = self.axes[index]
        QToolTip.showText(event.globalPosition().toPoint(),
                          f"{name}\nSIF potential: {sif}\nCritical risk: {critical}\n"
                          f"All reports: {total}", self)

    def leaveEvent(self, _event) -> None:  # noqa: N802
        if self.hover != -1:
            self.hover = -1
            self.update()
