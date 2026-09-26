"""An interactive risk map of the operating area, drawn with no network and no tiles.

Each site is a circle at its locality (:mod:`sif.geo`): its size is how many
reports it has, its colour how dense its SIF precursors are (or, switched,
how many reports). Around them, for orientation: the Brahmaputra and its
tributaries, the main roads, the towns, a latitude/longitude grid, a scale
bar and a north arrow.

* **Hover** a site for its figures; **click** it to choose it - the ranked
  table and the site's incidents, activities and barrier failures follow.
* **Scroll** to zoom about the pointer, **drag** to pan, **double-click** to
  fit every site again; the +, - and Fit buttons do the same.

The same interface as :class:`ui4.hotspots.SchematicMap` - ``set_sites`` and
the ``chosen`` signal - so the page's wiring does not change.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QSizePolicy, QToolTip, QWidget

from sif.geo import RIVERS, ROADS, TOWNS, km_per_degree, place_sites

__all__ = ["RiskMap", "density_colour", "DENSITY_STOPS"]

LAND = "#F4F2EC"
WATER = "#BFD7EA"
WATER_TEXT = "#5B87A8"
ROAD = "#D9D2C3"
GRID = "#E3DFD5"
TOWN = "#6B7280"
NAVY = "#1E3A5F"
#: Density 0 -> 100 %, light to deep: amber to red.
DENSITY_STOPS = ((0.0, (253, 230, 138)), (0.35, (251, 146, 60)), (0.65, (220, 38, 38)),
                 (1.0, (127, 29, 29)))
COUNT_STOPS = ((0.0, (191, 219, 254)), (0.5, (59, 130, 246)), (1.0, (30, 58, 95)))

#: The region shown when there is nothing to fit.
HOME = (26.85, 27.70, 94.55, 96.05)          # south, north, west, east


def _ramp(stops, fraction: float) -> QColor:
    fraction = max(0.0, min(1.0, fraction))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if fraction <= b:
            t = (fraction - a) / (b - a) if b > a else 0.0
            return QColor(*(round(x + (y - x) * t) for x, y in zip(ca, cb)))
    return QColor(*stops[-1][1])


def density_colour(percent: float) -> QColor:
    return _ramp(DENSITY_STOPS, percent / 100.0)


class RiskMap(QWidget):
    chosen = pyqtSignal(str)
    view_changed = pyqtSignal()

    MIN_SPAN = 0.08                       # degrees of latitude at the closest zoom
    MAX_SPAN = 3.0

    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.setMinimumHeight(420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.sites: List[Dict[str, object]] = []
        self.placed: Dict[str, Tuple[float, float, str]] = {}
        self.unplaced: List[str] = []
        self.selected = ""
        self.hover = ""
        self.colour_by = "density"
        self.centre = ((HOME[0] + HOME[1]) / 2, (HOME[2] + HOME[3]) / 2)
        self.span = HOME[1] - HOME[0]         # degrees of latitude from top to bottom
        self._drag: Optional[QPointF] = None
        self._drag_centre = self.centre
        self._moved = False
        self._fitted_for: Tuple[str, ...] = ()

    # -- data ---------------------------------------------------------------------------

    def set_sites(self, sites: Sequence[Dict[str, object]], selected: str) -> None:
        self.sites = list(sites)
        self.selected = selected
        self.placed, self.unplaced = place_sites([str(site["label"]) for site in self.sites])
        names = tuple(sorted(self.placed))
        if names != self._fitted_for:
            self._fitted_for = names
            self.fit()
        self.update()

    def set_colour_by(self, mode: str) -> None:
        self.colour_by = mode
        self.update()

    # -- the view ------------------------------------------------------------------------

    def fit(self) -> None:
        """Every placed site in view, with a margin; the home region if none."""
        points = [(lat, lon) for lat, lon, _ in self.placed.values()]
        if not points:
            south, north, west, east = HOME
        else:
            south = min(p[0] for p in points)
            north = max(p[0] for p in points)
            west = min(p[1] for p in points)
            east = max(p[1] for p in points)
        aspect = self._aspect()
        lat_span = (north - south) * 1.6 + 0.14
        lon_span_as_lat = (east - west) * 1.3 / aspect + 0.12
        self.span = max(self.MIN_SPAN, min(self.MAX_SPAN, max(lat_span, lon_span_as_lat, 0.35)))
        # Nudge the sites up, clear of the legend in the bottom corner.
        self.centre = ((south + north) / 2 - self.span * 0.07, (west + east) / 2)
        self.update()
        self.view_changed.emit()

    def zoom(self, factor: float, about: Optional[QPointF] = None) -> None:
        about = about or QPointF(self.width() / 2, self.height() / 2)
        lat, lon = self.to_geo(about)
        self.span = max(self.MIN_SPAN, min(self.MAX_SPAN, self.span / factor))
        # Keep the point under the pointer where it was.
        new_lat, new_lon = self.to_geo(about)
        self.centre = (self.centre[0] + lat - new_lat, self.centre[1] + lon - new_lon)
        self.update()
        self.view_changed.emit()

    def _lon_scale(self) -> float:
        """Degrees of longitude per degree of latitude on screen (keeps shapes true)."""
        return 1.0 / max(0.2, math.cos(math.radians(self.centre[0])))

    def _aspect(self) -> float:
        """Screen width over height, in latitude-degrees."""
        return max(1, self.width()) / max(1, self.height()) * self._lon_scale()

    def to_screen(self, lat: float, lon: float) -> QPointF:
        per = self.height() / self.span
        x = self.width() / 2 + (lon - self.centre[1]) / self._lon_scale() * per
        y = self.height() / 2 - (lat - self.centre[0]) * per
        return QPointF(x, y)

    def to_geo(self, point: QPointF) -> Tuple[float, float]:
        per = self.height() / self.span
        lon = self.centre[1] + (point.x() - self.width() / 2) / per * self._lon_scale()
        lat = self.centre[0] - (point.y() - self.height() / 2) / per
        return lat, lon

    # -- drawing -------------------------------------------------------------------------

    def _font(self, size: int, bold: bool = False) -> QFont:
        font = QFont(self.font())
        font.setPixelSize(size)
        font.setBold(bold)
        return font

    def _radius(self, reports: int) -> float:
        biggest = max((int(site.get("reports") or 0) for site in self.sites), default=1) or 1
        zoom = max(0.8, min(2.2, (HOME[1] - HOME[0]) / self.span))
        return (7 + 17 * math.sqrt(reports / biggest)) * (0.75 + 0.25 * zoom)

    def _fill(self, site: Dict[str, object]) -> QColor:
        if self.colour_by == "count":
            biggest = max((int(s.get("reports") or 0) for s in self.sites), default=1) or 1
            return _ramp(COUNT_STOPS, int(site.get("reports") or 0) / biggest)
        return density_colour(float(site.get("density") or 0.0))

    def _line(self, painter: QPainter, points, width: float, colour: str) -> None:
        path = QPainterPath()
        for index, (lat, lon) in enumerate(points):
            point = self.to_screen(lat, lon)
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        pen = QPen(QColor(colour), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(LAND))
        self._paint_grid(painter)
        zoom = (HOME[1] - HOME[0]) / self.span
        for _name, width, points in RIVERS:
            self._line(painter, points, width * max(0.7, min(2.0, zoom)), WATER)
        for points in ROADS:
            self._line(painter, points, 2.0, ROAD)
        painter.setFont(self._font(10))
        for name, width, points in RIVERS[:1]:
            mid = self.to_screen(*points[len(points) // 2])
            painter.setPen(QColor(WATER_TEXT))
            painter.drawText(QPointF(mid.x() + 10, mid.y() - 8), name)
        for name, lat, lon in TOWNS:
            point = self.to_screen(lat, lon)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(TOWN))
            painter.drawEllipse(point, 2.5, 2.5)
            painter.setPen(QColor(TOWN))
            painter.setFont(self._font(11))
            painter.drawText(QPointF(point.x() + 5, point.y() + 14), name)
        self._paint_sites(painter)
        self._paint_furniture(painter)

    def _paint_grid(self, painter: QPainter) -> None:
        step = 0.25 if self.span > 0.6 else 0.1 if self.span > 0.2 else 0.05
        south, west = self.to_geo(QPointF(0, self.height()))
        north, east = self.to_geo(QPointF(self.width(), 0))
        painter.setPen(QPen(QColor(GRID), 1))
        painter.setFont(self._font(9))
        lat = math.floor(south / step) * step
        while lat <= north:
            y = self.to_screen(lat, west).y()
            painter.setPen(QPen(QColor(GRID), 1))
            painter.drawLine(QPointF(0, y), QPointF(self.width(), y))
            painter.setPen(QColor("#A8A29E"))
            painter.drawText(QPointF(4, y - 3), f"{lat:.2f}°N")
            lat += step
        lon = math.floor(west / step) * step
        while lon <= east:
            x = self.to_screen(south, lon).x()
            painter.setPen(QPen(QColor(GRID), 1))
            painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))
            painter.setPen(QColor("#A8A29E"))
            painter.drawText(QPointF(x + 3, self.height() - 4), f"{lon:.2f}°E")
            lon += step

    def _sites_on_screen(self) -> List[Tuple[Dict[str, object], QPointF, float]]:
        """Each placed site's centre and radius on screen.

        Sites in one locality sit on a ring around it, measured in pixels so
        they never overlap whatever the zoom; zoomed in far enough, the ring is
        their true (approximate) spacing instead.
        """
        from sif.geo import LOCALITIES

        groups: Dict[str, List[Dict[str, object]]] = {}
        for site in self.sites:
            where = self.placed.get(str(site["label"]))
            if where is not None:
                groups.setdefault(where[2], []).append(site)
        shown = []
        for locality, members in groups.items():
            members.sort(key=lambda site: str(site["label"]))
            centre = self.to_screen(*LOCALITIES[locality])
            radii = [self._radius(int(site.get("reports") or 0)) for site in members]
            if len(members) == 1:
                shown.append((members[0], centre, radii[0]))
                continue
            ring = max(sum(radius * 2 + 6 for radius in radii) / (2 * math.pi), max(radii) + 6)
            for index, (site, radius) in enumerate(zip(members, radii)):
                where = self.placed[str(site["label"])]
                true = self.to_screen(where[0], where[1])
                offset = math.hypot(true.x() - centre.x(), true.y() - centre.y())
                if offset >= ring:
                    shown.append((site, true, radius))
                    continue
                angle = 2 * math.pi * index / len(members) - math.pi / 2
                shown.append((site, QPointF(centre.x() + ring * math.cos(angle),
                                            centre.y() + ring * math.sin(angle)), radius))
        # Bigger first, so small ones are drawn on top and stay clickable.
        return sorted(shown, key=lambda item: -item[2])

    def _paint_sites(self, painter: QPainter) -> None:
        shown = self._sites_on_screen()
        top = {str(site["label"]) for site in sorted(
            self.sites, key=lambda s: (-float(s.get("density") or 0),
                                       -int(s.get("reports") or 0)))[:2]}
        for site, point, radius in shown:
            label = str(site["label"])
            fill = self._fill(site)
            halo = QColor(fill)
            halo.setAlpha(60)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            painter.drawEllipse(point, radius + 5, radius + 5)
            painter.setBrush(fill)
            chosen = label == self.selected
            hovered = label == self.hover
            painter.setPen(QPen(QColor(NAVY if chosen else "#FFFFFF"),
                                3 if chosen else 2 if hovered else 1.5))
            painter.drawEllipse(point, radius, radius)
            count = str(int(site.get("reports") or 0))
            painter.setFont(self._font(11, True))
            painter.setPen(QColor("#FFFFFF") if fill.lightness() < 150 else QColor("#1F2937"))
            painter.drawText(QRectF(point.x() - radius, point.y() - radius, radius * 2, radius * 2),
                             Qt.AlignmentFlag.AlignCenter, count)
        # Labels last, so no circle covers one.
        for site, point, radius in shown:
            label = str(site["label"])
            chosen = label == self.selected
            hovered = label == self.hover
            if chosen or hovered or label in top or self.span < 0.5:
                font = self._font(11, chosen)
                painter.setFont(font)
                width = QFontMetrics(font).horizontalAdvance(label) + 10
                box = QRectF(point.x() + radius + 4, point.y() - 10, width, 20)
                painter.setPen(QPen(QColor("#E5E7EB"), 1))
                painter.setBrush(QColor(255, 255, 255, 235))
                painter.drawRoundedRect(box, 4, 4)
                painter.setPen(QColor(NAVY if chosen else "#1F2937"))
                painter.drawText(box, Qt.AlignmentFlag.AlignCenter, label)

    def _paint_furniture(self, painter: QPainter) -> None:
        # Legend, bottom left.
        legend = QRectF(12, self.height() - 92, 236, 74)
        painter.setPen(QPen(QColor("#E5E7EB"), 1))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawRoundedRect(legend, 6, 6)
        painter.setPen(QColor("#374151"))
        painter.setFont(self._font(10, True))
        painter.drawText(QPointF(legend.left() + 10, legend.top() + 17),
                         "Colour: SIF-precursor density" if self.colour_by == "density"
                         else "Colour: number of reports")
        bar = QRectF(legend.left() + 10, legend.top() + 25, 140, 9)
        stops = DENSITY_STOPS if self.colour_by == "density" else COUNT_STOPS
        for step in range(70):
            painter.fillRect(QRectF(bar.left() + step * 2, bar.top(), 2, bar.height()),
                             _ramp(stops, step / 69))
        painter.setFont(self._font(9))
        painter.setPen(QColor("#6B7280"))
        painter.drawText(QPointF(bar.left(), bar.bottom() + 12),
                         "0%" if self.colour_by == "density" else "fewest")
        painter.drawText(QPointF(bar.right() - 24, bar.bottom() + 12),
                         "100%" if self.colour_by == "density" else "most")
        painter.drawText(QPointF(legend.left() + 10, legend.bottom() - 8),
                         "Size: number of reports · positions approximate")
        # Scale bar, bottom right.
        km_lat, km_lon = km_per_degree(self.centre[0])
        per_km = self.height() / self.span / km_lat
        target = 60 / per_km
        nice = next((value for value in (1, 2, 5, 10, 20, 25, 50, 100) if value >= target), 100)
        length = nice * per_km
        right = self.width() - 18
        y = self.height() - 22
        painter.setPen(QPen(QColor("#374151"), 2))
        painter.drawLine(QPointF(right - length, y), QPointF(right, y))
        painter.drawLine(QPointF(right - length, y - 4), QPointF(right - length, y + 4))
        painter.drawLine(QPointF(right, y - 4), QPointF(right, y + 4))
        painter.setFont(self._font(10))
        painter.drawText(QRectF(right - length, y - 20, length, 14),
                         Qt.AlignmentFlag.AlignCenter, f"{nice} km")
        # North arrow, top right.
        top = QPointF(self.width() - 26, 16)
        arrow = QPolygonF([top, QPointF(top.x() - 7, top.y() + 18), QPointF(top.x(), top.y() + 13),
                           QPointF(top.x() + 7, top.y() + 18)])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#374151"))
        painter.drawPolygon(arrow)
        painter.setPen(QColor("#374151"))
        painter.setFont(self._font(10, True))
        painter.drawText(QRectF(top.x() - 8, top.y() + 18, 16, 14), Qt.AlignmentFlag.AlignCenter, "N")

    # -- interaction ---------------------------------------------------------------------------

    def site_at(self, point: QPointF) -> str:
        for site, centre, radius in reversed(self._sites_on_screen()):
            if math.hypot(point.x() - centre.x(), point.y() - centre.y()) <= radius + 3:
                return str(site["label"])
        return ""

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._drag = event.position()
        self._drag_centre = self.centre
        self._moved = False

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        point = event.position()
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if (point - self._drag).manhattanLength() > 4:
                self._moved = True
                per = self.height() / self.span
                dx = (point.x() - self._drag.x()) / per * self._lon_scale()
                dy = (point.y() - self._drag.y()) / per
                self.centre = (self._drag_centre[0] + dy, self._drag_centre[1] - dx)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.update()
            return
        label = self.site_at(point)
        if label != self.hover:
            self.hover = label
            self.setCursor(Qt.CursorShape.PointingHandCursor if label
                           else Qt.CursorShape.OpenHandCursor)
            self.update()
        if label:
            site = next(site for site in self.sites if str(site["label"]) == label)
            QToolTip.showText(event.globalPosition().toPoint(), self._tooltip(site), self)
        else:
            QToolTip.hideText()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag is not None and not self._moved:
            label = self.site_at(event.position())
            if label:
                self.selected = label
                self.chosen.emit(label)
                self.update()
        elif self._moved:
            self.view_changed.emit()
        self._drag = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if not self.site_at(event.position()):
            self.fit()

    def wheelEvent(self, event) -> None:  # noqa: N802
        steps = event.angleDelta().y() / 120
        if steps:
            self.zoom(1.25 ** steps, event.position())

    def leaveEvent(self, _event) -> None:  # noqa: N802
        self.hover = ""
        self.update()

    def _tooltip(self, site: Dict[str, object]) -> str:
        where = self.placed.get(str(site["label"]))
        return (f"<b>{site['label']}</b><br>"
                f"{int(site.get('reports') or 0)} report(s), "
                f"{int(site.get('sif_reports') or 0)} with fatal potential<br>"
                f"SIF-precursor density {float(site.get('density') or 0):.0f}% "
                f"(Wilson lower bound)<br>"
                f"Dominant rule: {site.get('top_rule', '-')}<br>"
                f"Dominant failed barrier: {site.get('top_barrier', '-')}<br>"
                f"Repeats: {site.get('repeats', '-')}"
                + (f"<br><span style='color:#6B7280'>near {where[2].title()} · "
                   "click to choose</span>" if where else ""))
