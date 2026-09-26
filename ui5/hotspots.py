"""Risk Hotspots with an interactive map of the operating area.

The two-workspace page's schematic becomes :class:`ui5.geomap.RiskMap`: the
sites at their localities in Upper Assam, sized by reports and coloured by
SIF-precursor density, with hover, click to choose, zoom and pan. Choosing a
site on the map or in the ranked table drives the same incidents, activity
and barrier panels as before.
"""

from __future__ import annotations

from typing import Dict, Sequence

from PyQt6.QtWidgets import QLabel, QPushButton

from ui4.hotspots import HOTSPOT_COLUMNS, HotspotsPage
from ui4.kit import Col, DesignTable, Segmented

from .geomap import RiskMap

__all__ = ["SentraHotspots", "MAP_TABLE_COLUMNS"]

#: Beside the map the table keeps what ranks a site; the barrier and the
#: repeats are in the site's panels below and in each circle's tooltip.
_BY_KEY = {column.key: column for column in HOTSPOT_COLUMNS}
MAP_TABLE_COLUMNS = (
    Col("rank", "#", 30),
    _BY_KEY["label"],
    Col("reports", "Reports", 72, align="right"),
    Col("sif_reports", "SIF", 40, align="right"),
    Col("density", "Density", 90, "bar", value=_BY_KEY["density"].value),
    Col("top_rule", "Dominant rule", 0),
)


class SentraHotspots(HotspotsPage):
    def __init__(self) -> None:
        super().__init__()
        # Every site on the map by default; the repeat thresholds stay available.
        self.minimum.blockSignals(True)
        self.minimum.insertItem(0, "Every site", 1)
        self.minimum.setCurrentIndex(0)
        self.minimum.blockSignals(False)
        self.clear_button = QPushButton("Clear filters")
        self.clear_button.setToolTip("All reports, every site, ranked by density")
        self.clear_button.clicked.connect(self.clear_filters)
        self.head.add(self.clear_button)

        # The schematic gives way to the map.
        self.map_card.title.setText("Risk map — Upper Assam operating area")
        body = self.map_card.body
        body.removeWidget(self.map)
        self.map.setParent(None)
        self.map.deleteLater()
        for index in range(self.map_card.head_actions.count()):
            item = self.map_card.head_actions.itemAt(index)
            if isinstance(item.widget(), QLabel) and item.widget() is not self.map_card.title \
                    and item.widget() is not self.map_card.caption:
                item.widget().hide()
        self.map = RiskMap()
        self.map.chosen.connect(self.site_chosen.emit)
        body.addWidget(self.map, 1)
        self.colour = Segmented((("density", "SIF density"), ("count", "Reports")), "density")
        self.colour.changed.connect(self.map.set_colour_by)
        self.map_card.add_head(self.colour)
        for text, tip, action in (("+", "Zoom in", lambda: self.map.zoom(1.5)),
                                  ("−", "Zoom out", lambda: self.map.zoom(1 / 1.5)),
                                  ("Fit", "Show every site", self.map.fit)):
            button = QPushButton(text)
            button.setObjectName("MapButton")
            button.setToolTip(tip)
            button.setFixedWidth(40 if text != "Fit" else 48)
            button.clicked.connect(action)
            self.map_card.add_head(button)
        self.unplaced = QLabel("")
        self.unplaced.setObjectName("CardCaption")
        self.unplaced.setWordWrap(True)
        self.unplaced.setContentsMargins(14, 6, 14, 8)
        body.addWidget(self.unplaced)
        self.map_card.caption.setText("hover for figures · click to choose · scroll to zoom · "
                                      "drag to pan")

        # A table that fits beside the map.
        self.ranked.body.removeWidget(self.table)
        self.table.setParent(None)
        self.table = DesignTable(MAP_TABLE_COLUMNS, row_height=40, wrap=True)
        self.table.row_clicked.connect(self._pick)
        self.ranked.body.insertWidget(0, self.table, 1)

        # The map gets the room a map needs.
        self.map_card.setMinimumHeight(520)
        self.ranked.setMinimumHeight(520)
        for index in range(self.body.count()):
            layout = self.body.itemAt(index).layout()
            if layout is not None and layout.indexOf(self.map_card) >= 0:
                layout.setStretch(layout.indexOf(self.map_card), 58)
                layout.setStretch(layout.indexOf(self.ranked), 42)

    def clear_filters(self) -> None:
        for box, index in ((self.period, 2), (self.minimum, 0)):
            box.blockSignals(True)
            box.setCurrentIndex(index)
            box.blockSignals(False)
        self.rank.select("density")
        self.filters_changed.emit()
        self.map.fit()

    def show_state(self, spots: Sequence[Dict[str, object]], selected: str, insight: str,
                   incidents, activities, barriers, dominant: str) -> None:
        super().show_state(spots, selected, insight, incidents, activities, barriers, dominant)
        unplaced = self.map.unplaced
        self.unplaced.setText(
            "Not on the map (no known locality in the name): " + ", ".join(unplaced)
            if unplaced else "")
        self.unplaced.setVisible(bool(unplaced))
