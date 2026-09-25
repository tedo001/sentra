"""The parts every page of the HSE application design is built from.

Taken from the design sheets: a page head (title, a mono caption on the same
line, actions on the right), white cards with a titled head over a hairline,
a strip of joined figures, status pills in five tones, tables whose risk
column carries a small bar and whose status column carries a pill, bar lists,
a trend line, segmented controls, underlined tabs, alert rows and a timeline.

Everything is styled by object name from :mod:`ui.workspace_theme`; the few
parts that are drawn (bars, the risk cell, pills inside a table, the trend
line) take their colours from :data:`TONES` and :func:`risk_colour` here, so a
colour is decided in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PyQt6.QtCore import QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath,
                         QPen)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

__all__ = ["AlertRow", "BarList", "Card", "Col", "DesignTable", "KeyValues", "LineChart",
           "Page", "PageHead", "Pill", "Segmented", "StatCell", "StatStrip", "TabbedCard",
           "Timeline", "TONES", "clear_layout", "link_button", "risk_colour", "scrolling"]

TEXT = "#1F2328"
MUTED = "#5F6368"
FAINT = "#8A8F95"
LINE = "#DCDDD8"
HAIR = "#E9EAE6"
NAVY = "#1E4F7A"
RED = "#B3261E"
BAR = "#44515A"
TRACK = "#E9EAE6"

#: tone -> (fill, text, border)
TONES: Dict[str, Tuple[str, str, str]] = {
    "ok": ("#EAF4EC", "#1E7B34", "#A8D5B2"),
    "warn": ("#FEF6E0", "#7A5200", "#EBCB82"),
    "fail": ("#FCEDEC", "#B3261E", "#E7B0AB"),
    "info": ("#E8EFF7", "#1E4F7A", "#A9C1D9"),
    "grey": ("#EEEEEB", "#45484D", "#D2D3CE"),
    "dark": ("#1E2327", "#FFFFFF", "#1E2327"),
    "engine": ("#FFFFFF", "#3C4043", "#9A9E99"),
}


def risk_colour(score: float) -> str:
    """The risk bar's colour: red at critical, rust, ochre, then a quiet green."""
    if score >= 85:
        return RED
    if score >= 70:
        return "#8E3B12"
    if score >= 40:
        return "#9A6A00"
    return "#4F7A5A"


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def scrolling(content: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setObjectName("PageScroll")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(content)
    return area


def link_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("Link")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFlat(True)
    return button


def _label(text: str, name: str, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


# ---------------------------------------------------------------------------
# page and card
# ---------------------------------------------------------------------------

class PageHead(QWidget):
    """Title, a mono caption on the same line, and actions on the right."""

    def __init__(self, title: str, caption: str = "") -> None:
        super().__init__()
        self.setObjectName("PageHeadBar")
        self.title = _label(title, "PageTitle")
        self.caption = _label(caption, "PageCaption", wrap=True)
        self.caption.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.title, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.caption, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(self.actions)

    def add(self, widget: QWidget) -> QWidget:
        self.actions.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return widget


class Page(QWidget):
    """A page of the application: its head, then its body on the grey ground."""

    def __init__(self, title: str, caption: str = "", *, scroll: bool = False) -> None:
        super().__init__()
        self.setObjectName("DesignPage")
        self.head = PageHead(title, caption)
        content = QWidget()
        content.setObjectName("PageBody")
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(12)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(12)
        outer.addWidget(self.head)
        if scroll:
            self.scroll = scrolling(content)
            outer.addWidget(self.scroll, 1)
        else:
            self.scroll = None
            outer.addWidget(content, 1)


class Card(QFrame):
    """White card: a head (title, caption, right-hand parts) over a hairline."""

    def __init__(self, title: str = "", caption: str = "", *, flush: bool = False,
                 margins: Tuple[int, int, int, int] = (14, 12, 14, 14)) -> None:
        super().__init__()
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.head = None
        if title:
            self.head = QFrame()
            self.head.setObjectName("CardHead")
            head = QHBoxLayout(self.head)
            head.setContentsMargins(14, 10, 12, 10)
            head.setSpacing(8)
            self.title = _label(title, "CardTitle")
            self.caption = _label(caption, "CardCaption")
            head.addWidget(self.title)
            head.addWidget(self.caption)
            head.addStretch(1)
            self.head_actions = head
            outer.addWidget(self.head)
        holder = QWidget()
        holder.setObjectName("CardBody")
        self.body = QVBoxLayout(holder)
        self.body.setContentsMargins(*((0, 0, 0, 0) if flush else margins))
        self.body.setSpacing(8)
        outer.addWidget(holder, 1)

    def add_head(self, widget: QWidget) -> QWidget:
        if self.head is not None:
            self.head_actions.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        return widget

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.body.addWidget(widget, stretch)
        return widget


class TabbedCard(QFrame):
    """A card whose head is a row of underlined tabs."""

    changed = pyqtSignal(int)

    def __init__(self, tabs: Sequence[str], right: Optional[QWidget] = None) -> None:
        super().__init__()
        self.setObjectName("Card")
        self.bar = QTabBar()
        self.bar.setObjectName("Underline")
        self.bar.setExpanding(False)
        self.bar.setDrawBase(False)
        for name in tabs:
            self.bar.addTab(name)
        self.pages = QStackedWidget()
        self.pages.setObjectName("CardBody")
        self.bar.currentChanged.connect(self.pages.setCurrentIndex)
        self.bar.currentChanged.connect(self.changed.emit)
        head = QFrame()
        head.setObjectName("TabHead")
        row = QHBoxLayout(head)
        row.setContentsMargins(8, 0, 12, 0)
        row.addWidget(self.bar, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        if right is not None:
            row.addWidget(right, 0, Qt.AlignmentFlag.AlignVCenter)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(head)
        outer.addWidget(self.pages, 1)

    def add_page(self, widget: QWidget) -> QWidget:
        self.pages.addWidget(widget)
        return widget


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------

class StatCell(QFrame):
    """One figure: a label, the value, and a note after it."""

    def __init__(self, label: str, *, mono: bool = False) -> None:
        super().__init__()
        self.setObjectName("StatCell")
        self.label = _label(label, "StatLabel")
        self.alert = _label("▲", "StatAlert")
        self.alert.hide()
        self.value = _label("-", "StatMono" if mono else "StatValue")
        self.note = _label("", "StatNote")
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.alert, 0, Qt.AlignmentFlag.AlignBaseline)
        row.addWidget(self.value, 0, Qt.AlignmentFlag.AlignBaseline)
        row.addWidget(self.note, 1, Qt.AlignmentFlag.AlignBaseline)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(2)
        layout.addWidget(self.label)
        layout.addLayout(row)

    def set(self, value: object, note: str = "", *, alert: bool = False) -> None:
        self.value.setText(str(value))
        self.note.setText(note)
        self.alert.setVisible(alert)
        self.value.setProperty("alert", alert)
        self.value.style().unpolish(self.value)
        self.value.style().polish(self.value)


class StatStrip(QFrame):
    """Figures side by side in one card, divided by hairlines."""

    def __init__(self, labels: Sequence[str], *, mono: bool = False) -> None:
        super().__init__()
        self.setObjectName("StatStrip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.cells: List[StatCell] = []
        for index, text in enumerate(labels):
            cell = StatCell(text, mono=mono)
            cell.setProperty("first", index == 0)
            self.cells.append(cell)
            layout.addWidget(cell, 1)


class Pill(QLabel):
    """A status in one of the tones: ok, warn, fail, info, grey, dark, engine."""

    def __init__(self, text: str = "", tone: str = "grey") -> None:
        super().__init__(text)
        self.setObjectName("Pill")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set(text, tone)

    def set(self, text: str, tone: str) -> None:
        self.setText(text)
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)


# ---------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------

@dataclass
class Col:
    """One column: ``kind`` decides how the cell is drawn.

    ``text`` ``strong`` ``mono`` ``muted`` ``num`` plain values; ``link`` a
    navy underlined reference; ``pill`` a ``(text, tone)`` pair; ``risk`` a
    score with its bar; ``bar`` a ``(value, fraction)`` pair drawn as a bar.
    """

    key: str
    title: str
    width: int = 0                     # 0 = stretch
    kind: str = "text"
    value: Optional[Callable[[Dict[str, object]], object]] = None
    align: str = "left"
    #: Optional per-row ink and weight: ``row -> (colour or "", bold)``.
    style: Optional[Callable[[Dict[str, object]], Tuple[str, bool]]] = None

    def read(self, row: Dict[str, object]) -> object:
        return self.value(row) if self.value is not None else row.get(self.key, "")


ROLE_KIND = Qt.ItemDataRole.UserRole + 1
ROLE_PAYLOAD = Qt.ItemDataRole.UserRole + 2


class _CellDelegate(QStyledItemDelegate):
    """Draws the cells a plain item cannot: pills, risk bars, bars and links."""

    def __init__(self, table: "DesignTable") -> None:
        super().__init__(table)
        self.table = table

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        kind = index.data(ROLE_KIND) or "text"
        if kind in ("text", "strong", "mono", "muted", "num"):
            super().paint(painter, option, index)
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Selection and hover ground, as the plain cells get it.
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#E6EEF7"))
        rect = option.rect.adjusted(10, 0, -8, 0)
        payload = index.data(ROLE_PAYLOAD)
        font = QFont(option.font)
        if kind == "link":
            font.setUnderline(True)
            font.setWeight(QFont.Weight.Medium)
            font.setFamily(self.table.mono_family)
            painter.setFont(font)
            painter.setPen(QColor(NAVY))
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             str(index.data(Qt.ItemDataRole.DisplayRole) or ""))
        elif kind == "pill" and payload:
            text, tone = payload
            fill, ink, border = TONES.get(tone, TONES["grey"])
            font.setPixelSize(12)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            metrics = QFontMetrics(font)
            width = metrics.horizontalAdvance(text) + 14
            height = metrics.height() + 6
            box = QRectF(rect.left(), rect.center().y() - height / 2 + 0.5, width, height)
            painter.setPen(QPen(QColor(border), 1))
            painter.setBrush(QColor(fill))
            painter.drawRoundedRect(box, 2, 2)
            painter.setPen(QColor(ink))
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
            extra = index.data(Qt.ItemDataRole.ToolTipRole + 100)
            if extra:
                painter.setPen(QColor(MUTED))
                painter.setFont(option.font)
                painter.drawText(QRectF(box.right() + 8, rect.top(), rect.width(), rect.height()),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 str(extra))
        elif kind == "risk":
            score = float(payload or 0.0)
            font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(TEXT))
            number = QRectF(rect.left(), rect.top(), 30, rect.height())
            painter.drawText(number, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                             f"{score:.0f}")
            track = QRectF(number.right() + 6, rect.center().y() - 2, 36, 4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(TRACK))
            painter.drawRoundedRect(track, 1, 1)
            filled = QRectF(track.left(), track.top(), max(2.0, track.width() * min(score, 100) / 100),
                            track.height())
            painter.setBrush(QColor(risk_colour(score)))
            painter.drawRoundedRect(filled, 1, 1)
        elif kind == "bar" and payload:
            value, fraction = payload
            painter.setFont(font)
            painter.setPen(QColor(TEXT))
            label = QRectF(rect.left(), rect.top(), 44, rect.height())
            painter.drawText(label, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             str(value))
            track = QRectF(label.right() + 2, rect.center().y() - 2, 34, 4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(TRACK))
            painter.drawRect(track)
            painter.setBrush(QColor(TEXT))
            painter.drawRect(QRectF(track.left(), track.top(),
                                    track.width() * max(0.0, min(1.0, float(fraction))), 4))
        # The row's hairline, which the style sheet draws for plain cells only.
        painter.setPen(QPen(QColor(HAIR), 1))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()


class DesignTable(QTableWidget):
    """A table in the design's manner: no grid, hairline rows, a light head."""

    row_clicked = pyqtSignal(int)
    row_activated = pyqtSignal(int)
    link_clicked = pyqtSignal(int)

    def __init__(self, columns: Sequence[Col], *, row_height: int = 34,
                 wrap: bool = False) -> None:
        super().__init__(0, len(columns))
        self.setObjectName("DesignTable")
        self.columns = list(columns)
        self.rows: List[Dict[str, object]] = []
        self.wrap = wrap
        self.row_height = row_height
        self.mono_family = "IBM Plex Mono"
        self.setHorizontalHeaderLabels([column.title for column in self.columns])
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(row_height)
        self.setShowGrid(False)
        self.setWordWrap(wrap)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setItemDelegate(_CellDelegate(self))
        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for index, column in enumerate(self.columns):
            if column.width:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
                self.setColumnWidth(index, column.width)
            else:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
            if column.align == "right":
                item = QTableWidgetItem(column.title)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setHorizontalHeaderItem(index, item)
        self.cellClicked.connect(self._clicked)
        self.cellDoubleClicked.connect(lambda row, _column: self.row_activated.emit(row))

    def _clicked(self, row: int, column: int) -> None:
        self.row_clicked.emit(row)
        if self.columns[column].kind == "link":
            self.link_clicked.emit(row)

    def set_rows(self, rows: Sequence[Dict[str, object]]) -> None:
        self.rows = list(rows)
        self.setUpdatesEnabled(False)
        self.clearContents()
        self.setRowCount(len(self.rows))
        mono = QFont(self.mono_family)
        for r, row in enumerate(self.rows):
            for c, column in enumerate(self.columns):
                value = column.read(row)
                item = QTableWidgetItem()
                item.setData(ROLE_KIND, column.kind)
                if column.kind == "pill":
                    pair = value if isinstance(value, tuple) else (str(value), "grey")
                    item.setData(ROLE_PAYLOAD, pair[:2])
                    if len(pair) > 2 and pair[2]:
                        item.setData(Qt.ItemDataRole.ToolTipRole + 100, pair[2])
                    item.setData(Qt.ItemDataRole.DisplayRole, "")
                elif column.kind == "risk":
                    item.setData(ROLE_PAYLOAD, float(value or 0.0))
                elif column.kind == "bar":
                    item.setData(ROLE_PAYLOAD, value)
                else:
                    item.setText("" if value is None else str(value))
                if column.kind in ("mono", "link"):
                    item.setFont(mono)
                if column.kind == "strong":
                    bold = QFont(item.font())
                    bold.setWeight(QFont.Weight.DemiBold)
                    item.setFont(bold)
                if column.kind == "muted":
                    item.setForeground(QColor(MUTED))
                if column.style is not None:
                    colour, bold = column.style(row)
                    if colour:
                        item.setForeground(QColor(colour))
                    if bold:
                        heavy = QFont(item.font())
                        heavy.setWeight(QFont.Weight.DemiBold)
                        item.setFont(heavy)
                align = (Qt.AlignmentFlag.AlignRight if column.align == "right"
                         else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(r, c, item)
        if self.wrap:
            self.resizeRowsToContents()
            for r in range(self.rowCount()):
                self.setRowHeight(r, max(self.row_height, self.rowHeight(r) + 8))
        self.setUpdatesEnabled(True)


# ---------------------------------------------------------------------------
# charts
# ---------------------------------------------------------------------------

class BarList(QWidget):
    """Label, bar, value - one row each, bars scaled to the largest value."""

    ROW = 25

    def __init__(self, *, label_ratio: float = 0.42, tone: str = BAR) -> None:
        super().__init__()
        self.items: List[Tuple[str, float, str]] = []
        self.label_ratio = label_ratio
        self.tone = tone
        self.empty = "Nothing to show yet."
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_items(self, items: Sequence[Tuple[str, float]], colours: Sequence[str] = ()) -> None:
        self.items = [(str(label), float(value), colours[i] if i < len(colours) else self.tone)
                      for i, (label, value) in enumerate(items)]
        self.updateGeometry()
        self.update()

    def _heights(self, width: int) -> List[int]:
        metrics = QFontMetrics(self.font())
        label_width = int(width * self.label_ratio) - 8
        heights = []
        for label, _value, _colour in self.items:
            box = metrics.boundingRect(QRect(0, 0, max(40, label_width), 1000),
                                       Qt.TextFlag.TextWordWrap, label)
            heights.append(max(self.ROW, box.height() + 7))
        return heights

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt's name
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return max(self.ROW, sum(self._heights(width))) + 4

    def sizeHint(self) -> QSize:
        return QSize(300, self.heightForWidth(max(300, self.width())))

    def minimumSizeHint(self) -> QSize:
        return QSize(160, self.heightForWidth(max(300, self.width())))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        if not self.items:
            painter.setPen(QColor(FAINT))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                             self.empty)
            return
        label_width = int(width * self.label_ratio)
        value_width = 38
        bar_left = label_width
        bar_width = max(20, width - label_width - value_width - 12)
        top = 0
        largest = max(value for _label, value, _colour in self.items) or 1.0
        for (label, value, colour), height in zip(self.items, self._heights(width)):
            painter.setPen(QColor(TEXT))
            painter.drawText(QRect(0, top, label_width - 8, height),
                             Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, label)
            track = QRectF(bar_left, top + height / 2 - 6, bar_width, 12)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(TRACK))
            painter.drawRect(track)
            painter.setBrush(QColor(colour))
            painter.drawRect(QRectF(track.left(), track.top(),
                                    max(2.0, bar_width * value / largest), 12))
            painter.setPen(QColor(TEXT))
            painter.drawText(QRect(int(track.right()) + 4, top, value_width, height),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                             f"{value:g}")
            top += height

    def resizeEvent(self, event) -> None:  # noqa: N802
        self.updateGeometry()
        super().resizeEvent(event)


class LineChart(QWidget):
    """Weekly series as lines: solid dark and dashed red, as the design draws them."""

    def __init__(self) -> None:
        super().__init__()
        self.series: List[Tuple[List[float], str, bool]] = []
        self.labels: Tuple[str, str, str] = ("", "", "")
        self.setMinimumHeight(180)

    def set_series(self, series: Sequence[Tuple[Sequence[float], str, bool]],
                   labels: Tuple[str, str, str]) -> None:
        self.series = [(list(values), colour, dashed) for values, colour, dashed in series]
        self.labels = labels
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(4, 8, self.width() - 8, self.height() - 34)
        painter.setPen(QPen(QColor(HAIR), 1))
        for step in range(4):
            y = area.top() + area.height() * step / 3
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
        values = [value for points, _colour, _dashed in self.series for value in points]
        if not values or all(value == 0 for value in values):
            painter.setPen(QColor(FAINT))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, "No dated reports yet.")
        else:
            top = max(values) * 1.15 or 1.0
            for points, colour, dashed in self.series:
                if len(points) < 2:
                    continue
                pen = QPen(QColor(colour), 2)
                if dashed:
                    pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                path = QPainterPath()
                for index, value in enumerate(points):
                    point = QPointF(area.left() + area.width() * index / (len(points) - 1),
                                    area.bottom() - area.height() * value / top)
                    if index == 0:
                        path.moveTo(point)
                    else:
                        path.lineTo(point)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
        mono = QFont("IBM Plex Mono")
        mono.setPixelSize(12)
        painter.setFont(mono)
        painter.setPen(QColor(MUTED))
        base = QRectF(area.left(), area.bottom() + 8, area.width(), 20)
        left, middle, right = self.labels
        painter.drawText(base, Qt.AlignmentFlag.AlignLeft, left)
        painter.drawText(base, Qt.AlignmentFlag.AlignHCenter, middle)
        painter.drawText(base, Qt.AlignmentFlag.AlignRight, right)


# ---------------------------------------------------------------------------
# controls
# ---------------------------------------------------------------------------

class Segmented(QFrame):
    """Joined options, one chosen - dark when chosen."""

    changed = pyqtSignal(str)

    def __init__(self, options: Sequence[Tuple[str, str]], current: str = "") -> None:
        super().__init__()
        self.setObjectName("Segmented")
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: Dict[str, QPushButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for index, (key, label) in enumerate(options):
            button = QPushButton(label)
            button.setObjectName("Seg")
            button.setCheckable(True)
            button.setProperty("edge", "first" if index == 0 else
                               "last" if index == len(options) - 1 else "mid")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked, name=key: self._choose(name))
            self.group.addButton(button)
            self.buttons[key] = button
            layout.addWidget(button)
        self.current = current or (options[0][0] if options else "")
        if self.current in self.buttons:
            self.buttons[self.current].setChecked(True)

    def _choose(self, key: str) -> None:
        self.current = key
        self.changed.emit(key)

    def select(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)
            self.current = key


class KeyValues(QWidget):
    """Label and value pairs in columns - the design's field lists."""

    def __init__(self, columns: int = 1, *, label_width: int = 110) -> None:
        super().__init__()
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(8)
        self.columns = columns
        self.label_width = label_width
        self.values: Dict[str, QLabel] = {}

    def set_pairs(self, pairs: Sequence[Tuple[str, str]], mono: Sequence[str] = (),
                  stacked: bool = False) -> None:
        clear_layout(self.grid)
        self.values = {}
        for index, (name, value) in enumerate(pairs):
            row, column = divmod(index, self.columns)
            key = _label(name, "KvKey")
            val = _label(value, "KvMono" if name in mono else "KvValue", wrap=True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.values[name] = val
            if stacked:
                box = QVBoxLayout()
                box.setSpacing(2)
                box.addWidget(key)
                box.addWidget(val)
                self.grid.addLayout(box, row, column)
            else:
                key.setFixedWidth(self.label_width)
                self.grid.addWidget(key, row, column * 2, Qt.AlignmentFlag.AlignTop)
                self.grid.addWidget(val, row, column * 2 + 1)
        for column in range(self.columns * (1 if stacked else 2)):
            self.grid.setColumnStretch(column, 0 if (not stacked and column % 2 == 0) else 1)


class AlertRow(QFrame):
    """A line that needs someone: a mark, a bold lead, the detail, one action."""

    MARKS = {"critical": "▲", "warn": "◆", "fail": "✕", "info": "●"}
    clicked = pyqtSignal()

    def __init__(self, tone: str, lead: str, text: str, action: str = "") -> None:
        super().__init__()
        self.setObjectName("Alert")
        self.setProperty("tone", tone)
        mark = _label(self.MARKS.get(tone, "●"), "AlertMark")
        mark.setProperty("tone", tone)
        mark.setFixedWidth(18)
        body = _label(f"<b>{lead}</b> {text}", "AlertText", wrap=True)
        body.setTextFormat(Qt.TextFormat.RichText)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 10, 8)
        layout.setSpacing(12)
        layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(body, 1, Qt.AlignmentFlag.AlignVCenter)
        self.button = None
        if action:
            self.button = QPushButton(action)
            self.button.clicked.connect(self.clicked.emit)
            layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignVCenter)


class Timeline(QWidget):
    """Times down the left, what happened on the right, a hairline between."""

    def __init__(self) -> None:
        super().__init__()
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(0)
        self.empty = "Nothing yet today."

    def set_items(self, items: Sequence[Tuple[str, str, str]]) -> None:
        clear_layout(self.layout_)
        if not items:
            self.layout_.addWidget(_label(self.empty, "Faint"))
        for when, text, sub in items:
            row = QFrame()
            row.setObjectName("TimelineRow")
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 8, 0, 8)
            line.setSpacing(14)
            stamp = _label(when, "TimelineTime")
            stamp.setFixedWidth(48)
            line.addWidget(stamp, 0, Qt.AlignmentFlag.AlignTop)
            words = QVBoxLayout()
            words.setSpacing(2)
            words.addWidget(_label(text, "TimelineText", wrap=True))
            if sub:
                words.addWidget(_label(sub, "TimelineSub", wrap=True))
            line.addLayout(words, 1)
            self.layout_.addWidget(row)
        self.layout_.addStretch(1)
