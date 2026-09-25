"""Risk Hotspots - where the repeats are, ranked by density rather than volume.

From the design: a period, a minimum number of reports and the ranking
(density or count); a schematic of the operating area in which each site is
a circle sized by its reports and shaded by its SIF-precursor density; the
ranked table with its dominant rule, dominant failed barrier and how often
that barrier repeats; and, for the chosen site, its incidents, its
activities and its barrier failures.

The schematic is explicitly not a map: there are no coordinates in a
near-miss export, so sites are placed around the busiest one, which is what
the design's own "not to scale" note says.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget

from .kit import BarList, Card, Col, DesignTable, Page, Segmented

__all__ = ["HOTSPOT_COLUMNS", "HotspotsPage", "SchematicMap"]

HOTSPOT_COLUMNS = (
    Col("rank", "#", 36),
    Col("label", "Location", 0, style=lambda row: ("", bool(row.get("_selected")))),
    Col("reports", "Reports", 70, align="right"),
    Col("sif_reports", "SIF", 50, align="right"),
    Col("density", "Density", 96, "bar",
        value=lambda row: (f"{row.get('density', 0):.0f}%", row.get("density", 0) / 100)),
    Col("top_rule", "Dominant rule", 150),
    Col("top_barrier", "Dominant failed barrier", 180),
    Col("repeats", "Repeats", 92),
)

INCIDENT_COLUMNS = (
    Col("reference", "Ref", 100, "mono"),
    Col("date", "Date", 76, "mono"),
    Col("what", "What happened", 0),
    Col("risk", "Risk", 50, align="right"),
)


#: How the schematic colours a site. "shade" runs light grey to near-black with
#: density; "opacity" keeps one grey and lets density set how solid it is, with
#: the chosen site in the selected colour. A theme's prepare() sets this.
SCHEME: Dict[str, object] = {"mode": "shade", "light": (213, 216, 218), "dark": (43, 47, 51),
                             "base": "#6B7280", "selected": "#1E4F7A", "ring": "#1E4F7A"}
SCHEME_DEFAULT = dict(SCHEME)


def _shade(density: float, chosen: bool = False) -> QColor:
    """A site's fill for its SIF-precursor density."""
    t = max(0.0, min(1.0, density / 100.0))
    if SCHEME["mode"] == "opacity":
        colour = QColor(str(SCHEME["selected"] if chosen else SCHEME["base"]))
        colour.setAlphaF(min(1.0, 0.5 + t))
        return colour
    light, dark = SCHEME["light"], SCHEME["dark"]
    return QColor(*(int(a + (b - a) * t) for a, b in zip(light, dark)))


class SchematicMap(QWidget):
    """Sites as circles around the busiest one, joined by trunk lines."""

    chosen = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.sites: List[Dict[str, object]] = []
        self.selected = ""
        self._hits: List[Tuple[QPointF, float, str]] = []
        self.setMinimumHeight(260)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_sites(self, sites: Sequence[Dict[str, object]], selected: str) -> None:
        self.sites = list(sites)[:9]
        self.selected = selected
        self.update()

    def _layout(self) -> List[Tuple[Dict[str, object], QPointF, float]]:
        if not self.sites:
            return []
        busiest = max(self.sites, key=lambda site: int(site.get("reports") or 0))
        largest = max(int(site.get("reports") or 1) for site in self.sites) or 1
        area = QRectF(30, 20, self.width() - 60, self.height() - 60)
        centre = area.center()
        placed = []
        others = [site for site in self.sites if site is not busiest]
        for index, site in enumerate([busiest] + others):
            radius = 12 + 16 * math.sqrt(int(site.get("reports") or 1) / largest)
            if index == 0:
                point = centre
            else:
                angle = -math.pi / 2 + 2 * math.pi * (index - 1) / max(1, len(others)) + 0.35
                point = QPointF(centre.x() + math.cos(angle) * area.width() * 0.40,
                                centre.y() + math.sin(angle) * area.height() * 0.40)
            placed.append((site, point, radius))
        return placed

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FAFAF8"))
        placed = self._layout()
        self._hits = []
        if not placed:
            painter.setPen(QColor("#8A8F95"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No site has enough reports to be a hotspot yet.")
            return
        hub = placed[0][1]
        painter.setPen(QPen(QColor("#D5D8DA"), 3))
        for _site, point, _radius in placed[1:]:
            painter.drawLine(hub, point)
        label_font = QFont(self.font())
        label_font.setPixelSize(11)
        for site, point, radius in placed:
            label = str(site.get("label"))
            painter.setPen(QPen(QColor(str(SCHEME["ring"])), 3 if SCHEME["mode"] == "shade" else 2)
                           if label == self.selected else Qt.PenStyle.NoPen)
            painter.setBrush(_shade(float(site.get("density") or 0), label == self.selected))
            painter.drawEllipse(point, radius, radius)
            painter.setFont(label_font)
            painter.setPen(QColor("#3C4043"))
            painter.drawText(QRectF(point.x() - 95, point.y() + radius + 2, 190, 16),
                             Qt.AlignmentFlag.AlignHCenter,
                             label if len(label) <= 30 else label[:29] + "\u2026")
            self._hits.append((point, radius, label))
        from . import kit

        mono = QFont(kit.MONO_FAMILY)
        mono.setPixelSize(11)
        painter.setFont(mono)
        painter.setPen(QColor("#5F6368"))
        painter.drawText(QRectF(10, self.height() - 22, self.width(), 18),
                         Qt.AlignmentFlag.AlignLeft,
                         "Not to scale · grey lines = trunk pipelines")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        for point, radius, label in self._hits:
            if math.hypot(event.position().x() - point.x(), event.position().y() - point.y()) \
                    <= radius + 4:
                self.chosen.emit(label)
                return


class HotspotsPage(Page):
    filters_changed = pyqtSignal()
    site_chosen = pyqtSignal(str)
    review_requested = pyqtSignal(str)
    report_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__("Risk Hotspots",
                         "Repeats ranked by SIF-precursor density, not by report count",
                         scroll=True)
        self.period = QComboBox()
        for key, label in (("30", "Last 30 days"), ("90", "Last 90 days"), ("0", "All reports")):
            self.period.addItem(label, key)
        self.period.setCurrentIndex(2)
        self.minimum = QComboBox()
        for count in (2, 3, 5):
            self.minimum.addItem(f"At least {count} reports", count)
        self.rank = Segmented((("density", "Rank by density"), ("count", "Rank by count")))
        for box in (self.period, self.minimum):
            box.currentIndexChanged.connect(lambda _i: self.filters_changed.emit())
        self.rank.changed.connect(lambda _key: self.filters_changed.emit())
        for widget in (self.period, self.minimum, self.rank):
            self.head.add(widget)

        self.map_card = Card("Operating area — schematic", "")
        legend = QLabel("circle = reports · shade = density")
        legend.setObjectName("CardCaption")
        self.map_card.add_head(legend)
        self.map = SchematicMap()
        self.map.chosen.connect(self.site_chosen.emit)
        self.map_card.body.setContentsMargins(0, 0, 0, 0)
        self.map_card.add(self.map, 1)

        self.ranked = Card("Ranked hotspots", "", flush=True)
        note = QLabel("density = lower bound of SIF share (Wilson 95%)")
        note.setObjectName("CardCaption")
        self.ranked.add_head(note)
        self.table = DesignTable(HOTSPOT_COLUMNS, row_height=44, wrap=True)
        self.table.row_clicked.connect(self._pick)
        self.ranked.add(self.table, 1)
        self.insight = QLabel("")
        self.insight.setObjectName("Insight")
        self.insight.setWordWrap(True)
        self.ranked.add(self.insight)

        self.incidents = Card("Repeated incidents", "", flush=True)
        self.open_review = QPushButton("Open in Review")
        self.open_review.clicked.connect(self._to_review)
        self.incidents.add_head(self.open_review)
        self.incident_table = DesignTable(INCIDENT_COLUMNS, row_height=30)
        self.incident_table.row_activated.connect(self._open_report)
        self.incidents.add(self.incident_table, 1)

        self.activities = Card("Activity breakdown", "")
        self.activity_count = QLabel("")
        self.activity_count.setObjectName("CardCaption")
        self.activities.add_head(self.activity_count)
        self.activity_bars = BarList(label_ratio=0.38)
        self.activities.add(self.activity_bars)
        self.activities.body.addStretch(1)

        self.barriers = Card("Barrier failures", "")
        repeat = QLabel("repeat = same barrier ≥ 2")
        repeat.setObjectName("CardCaption")
        self.barriers.add_head(repeat)
        self.barrier_bars = BarList(label_ratio=0.38)
        self.barriers.add(self.barrier_bars)
        self.dominant = QLabel("")
        self.dominant.setObjectName("CardCaption")
        self.dominant.setWordWrap(True)
        self.barriers.add(self.dominant)
        self.barriers.body.addStretch(1)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self.map_card, 41)
        top.addWidget(self.ranked, 57)
        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        bottom.addWidget(self.incidents, 38)
        bottom.addWidget(self.activities, 29)
        bottom.addWidget(self.barriers, 29)
        for card in (self.map_card, self.ranked):
            card.setMinimumHeight(340)
        for card in (self.incidents, self.activities, self.barriers):
            card.setMinimumHeight(280)
        self.body.addLayout(top)
        self.body.addLayout(bottom, 1)
        self.selected = ""

    @property
    def filters(self) -> Tuple[int, int, str]:
        return (int(self.period.currentData()), int(self.minimum.currentData()),
                self.rank.current)

    def _pick(self, index: int) -> None:
        if 0 <= index < len(self.table.rows):
            self.site_chosen.emit(str(self.table.rows[index].get("label")))

    def _to_review(self) -> None:
        rows = self.incident_table.rows
        self.review_requested.emit(str(rows[0].get("reference")) if rows else "")

    def _open_report(self, index: int) -> None:
        if 0 <= index < len(self.incident_table.rows):
            self.report_requested.emit(str(self.incident_table.rows[index].get("reference")))

    def select_label(self, label: str) -> None:
        self.site_chosen.emit(label)

    def show_state(self, spots: Sequence[Dict[str, object]], selected: str, insight: str,
                   incidents: Sequence[Dict[str, object]], activities, barriers,
                   dominant: str) -> None:
        self.selected = selected
        rows = [{**spot, "_selected": spot.get("label") == selected} for spot in spots]
        self.table.set_rows(rows)
        for index, row in enumerate(rows):
            if row["_selected"]:
                self.table.selectRow(index)
        self.map.set_sites(spots, selected)
        self.insight.setText(insight)
        self.insight.setVisible(bool(insight))
        self.incidents.title.setText(f"Repeated incidents · {selected}" if selected
                                     else "Repeated incidents")
        self.incident_table.set_rows(incidents)
        self.open_review.setEnabled(bool(incidents))
        self.activity_count.setText(f"{len(incidents)} reports" if selected else "")
        self.activity_bars.set_items(activities)
        self.barrier_bars.set_items([(label, count) for label, count in barriers],
                                    ["#1E2327" if count >= 2 else "#9EA3A7"
                                     for _label, count in barriers])
        self.dominant.setText(dominant)
