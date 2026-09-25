"""The two-workspace skin: the design in the Stage 1 and Stage 2 sheets.

A dark title row across the top, a light tab row beneath it, and content on a
warm grey page. Two variants share everything but the tab row:

``HSE workspace``   white tab row; the selected tab is underlined in navy
``Administration``  an amber rule along the top of the header, a warm cream
                    tab row, an amber ADMINISTRATION tag and an amber
                    underline - so an administrator can tell which workspace
                    they are in from the edge of the screen

Type is IBM Plex Sans with Plex Mono for the machine-facing text (the project
code, the host and build, the time of the last run), as the sheets set it, and
the platform's own sans behind each where Plex is not installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .theme import ASSETS as _ASSETS

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PyQt6.QtWidgets import QMainWindow

__all__ = ["PALETTE", "STYLESHEET", "NAME", "HEADER", "NAVY", "AMBER", "CREAM",
           "FONT", "MONO", "load_fonts", "prepare", "dress"]

NAME = "Two workspaces"

#: The sheets' own colours.
HEADER = "#1E2327"           # the title row
NAVY = "#1E4F7A"             # HSE: selected tab, review badge, primary action
AMBER = "#CD881A"            # Administration: rule, tag, selected tab
CREAM = "#F7F3EA"            # Administration: the tab row
PAGE = "#F1F2ED"             # the page behind the cards
LINE = "#DCDDD8"             # card edges
HAIR = "#E9EAE6"             # rules between rows

FONT = '"IBM Plex Sans", "Segoe UI", "Inter", "DejaVu Sans", Arial, sans-serif'
MONO = '"IBM Plex Mono", "Consolas", "DejaVu Sans Mono", monospace'

PALETTE = {
    "APP": PAGE,
    "SIDEBAR": "#FFFFFF",
    "HEADER": HEADER,
    "PANEL": "#FFFFFF",
    "PANEL_ALT": "#F7F7F4",
    "CARD": "#FFFFFF",
    "BORDER": LINE,
    "BORDER_SOFT": "#E8E9E5",
    "TEXT": "#1F2328",
    "TEXT_DIM": "#5F6368",
    "TEXT_FAINT": "#8A8F95",
    "BRAND": "#C62828",
    "ACCENT": NAVY,
    "ACCENT_SOFT": "#2F6699",
    "ACCENT_DIM": "#173A5A",
    "BLUE": "#2F6699",
    "PURPLE": "#6A4C93",
    "ICON_ON": "#1F2328",
    "SCROLL_TRACK": PAGE,
    "SCROLL_THUMB": "#C4C7C2",
    "SCROLL_THUMB_HOVER": "#9A9E99",
    "DANGER": "#C62828",
    "WARN": "#B26A00",
    "OK": "#2E7D32",
    "INFO": NAVY,
    "RAIL_WASH": "#FFFFFF",
    "RAIL_LINE": LINE,
    "RAIL_ACCENT": NAVY,
}

_C = PALETTE

STYLESHEET = f"""
/* Transparent by default: a plain container shows whatever it sits on - the
   page, a card, the header - so no card needs a rule to clear its children,
   and no such rule can outrank a button's own fill. Surfaces say their colour. */
QWidget {{
    background-color: transparent;
    color: {_C["TEXT"]};
    font-family: {FONT};
    font-size: 14px;
}}
QMainWindow, QDialog {{ background-color: {PAGE}; }}
QDialog {{ background-color: #FFFFFF; }}
QLabel {{ background: transparent; border: none; }}

/* ---- the title row ---------------------------------------------------
   Everything inside the header is cleared to transparent, so each piece that
   has a fill of its own - the badge, the avatar, the tag - is named under the
   header too; a bare QLabel#Badge would lose to the broader rule. */
QFrame#WorkspaceHeader {{ background-color: {HEADER}; border: none; }}
QFrame#WorkspaceHeader[workspace="admin"] {{ border-top: 3px solid {AMBER}; }}
QFrame#WorkspaceHeader QWidget {{ background: transparent; color: #FFFFFF; }}
QFrame#WorkspaceHeader QLabel#OilMark {{
    border: 1.5px solid #C9CCD1;
    border-radius: 15px;
    color: #FFFFFF;
    font-family: {MONO};
    font-size: 9px;
    font-weight: 600;
}}
QFrame#WorkspaceHeader QLabel#OilLogo {{
    background-color: #FFFFFF;
    border-radius: 4px;
    padding: 2px 4px;
}}
QLabel#OrgName {{ font-size: 14px; font-weight: 600; color: #FFFFFF; }}
QFrame#WorkspaceHeader QLabel#OrgPlace {{ font-size: 11px; color: #A9ADB3; }}
QLabel#Wordmark {{
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 6px;
    color: #FFFFFF;
}}
QFrame#WorkspaceHeader QLabel#WorkspaceTag {{
    font-family: {MONO};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    color: #E6E8EB;
    border: 1px solid #8C9096;
    border-radius: 2px;
    padding: 2px 6px;
}}
QFrame#WorkspaceHeader QLabel#WorkspaceTag[workspace="admin"] {{ color: #F2B84B; border-color: {AMBER}; }}
QFrame#WorkspaceHeader QLabel#ProjectCode {{ font-family: {MONO}; font-size: 12px; color: #D5D8DC; }}
QToolButton#HeaderIcon {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px;
}}
QToolButton#HeaderIcon:hover {{ background: rgba(255, 255, 255, 0.10); }}
QFrame#WorkspaceHeader QLabel#Badge {{
    background-color: #D93025;
    color: #FFFFFF;
    border-radius: 7px;
    font-size: 9px;
    font-weight: 700;
    padding: 0px 4px;
}}
QFrame#WorkspaceHeader QLabel#Avatar {{
    background-color: #3A3F46;
    color: #FFFFFF;
    border-radius: 14px;
    font-size: 11px;
    font-weight: 700;
}}
QLabel#UserName {{ font-size: 13px; font-weight: 600; color: #FFFFFF; }}
QFrame#WorkspaceHeader QLabel#UserRole {{ font-size: 11px; color: #A9ADB3; }}
QPushButton#AccountButton {{
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 2px 6px;
    text-align: left;
}}
QPushButton#AccountButton:hover {{ background: rgba(255, 255, 255, 0.08); }}

/* ---- the tab row ------------------------------------------------------ */
QFrame#TabRow {{ background-color: #FFFFFF; border-bottom: 1px solid {LINE}; }}
QFrame#TabRow[workspace="admin"] {{ background-color: {CREAM}; }}
QFrame#TabRow QWidget {{ background: transparent; }}
QPushButton#WorkspaceTab {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0px;
    padding: 11px 14px 9px 14px;
    font-size: 14px;
    font-weight: 400;
    color: #3C4043;
}}
QPushButton#WorkspaceTab:hover {{ color: #111111; border-bottom-color: #C4C7C2; }}
QPushButton#WorkspaceTab:checked {{
    color: #111111;
    font-weight: 600;
    border-bottom: 2px solid {NAVY};
}}
QFrame#TabRow[workspace="admin"] QPushButton#WorkspaceTab:checked {{
    border-bottom: 2px solid {AMBER};
}}
QFrame#TabRow QLabel#TabBadge {{
    background-color: {NAVY};
    color: #FFFFFF;
    border-radius: 2px;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 5px;
}}
QFrame#TabRow QLabel#TabNote {{ font-family: {MONO}; font-size: 12px; color: #5F6368; }}

/* ---- pages -------------------------------------------------------------- */
QFrame#PageHead {{
    background-color: {PAGE};
    border-bottom: 1px solid {LINE};
    padding-bottom: 10px;
}}
QFrame#Footer {{ background-color: #FFFFFF; border-top: 1px solid {LINE}; }}
QFrame#Panel, QFrame#Card, QFrame#Tile {{
    background-color: #FFFFFF;
    border: 1px solid {LINE};
    border-radius: 3px;
}}
QLabel#PageTitle {{ font-size: 24px; font-weight: 600; }}
QLabel#SectionTitle {{ font-size: 19px; font-weight: 600; color: #1F2328; }}
QLabel#Caption {{
    font-family: {MONO};
    font-size: 10px;
    font-weight: 500;
    color: #5F6368;
    letter-spacing: 1.2px;
}}
QLabel#Muted {{ color: #5F6368; }}
QLabel#Faint {{ color: #8A8F95; font-size: 12px; }}
QLabel#KpiValue {{ font-size: 28px; font-weight: 600; }}
QLabel#KpiUnit {{ font-size: 12px; color: #5F6368; }}
QLabel#BrandName {{ font-size: 14px; font-weight: 600; }}

QPushButton {{
    background-color: #FFFFFF;
    border: 1px solid #C4C7C2;
    border-radius: 3px;
    padding: 7px 14px;
    font-weight: 500;
    color: #1F2328;
}}
QPushButton:hover {{ background-color: #F4F5F2; border-color: {NAVY}; color: {NAVY}; }}
QPushButton:pressed {{ background-color: #E9EBE7; }}
QPushButton:disabled {{ color: #A3A7AC; border-color: #E0E2DE; background: #FAFAF8; }}
QPushButton#Primary {{
    background-color: {NAVY};
    border: 1px solid {NAVY};
    color: #FFFFFF;
}}
QPushButton#Primary:hover {{ background-color: #173A5A; border-color: #173A5A; color: #FFFFFF; }}
QPushButton#Primary:disabled {{ background-color: #9DB3C9; border-color: #9DB3C9; color: #FFFFFF; }}
QPushButton#Warning {{
    background-color: #FFFFFF;
    border: 1px solid #C62828;
    color: #C62828;
}}
QPushButton#Warning:hover {{ background-color: #C62828; color: #FFFFFF; }}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QDateEdit {{
    background-color: #FFFFFF;
    border: 1px solid #C4C7C2;
    border-radius: 3px;
    padding: 7px 9px;
    color: #1F2328;
    selection-background-color: {NAVY};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDateEdit:focus {{
    border: 1px solid {NAVY};
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url({_ASSETS}/arrow_down.png); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background-color: #FFFFFF;
    border: 1px solid {LINE};
    selection-background-color: #EEF2F6;
    selection-color: #1F2328;
}}
QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid #9A9E99;
    border-radius: 2px;
    background-color: #FFFFFF;
}}
QCheckBox::indicator:checked {{
    background-color: {NAVY};
    border-color: {NAVY};
    image: url({_ASSETS}/check.svg);
}}

QTableWidget {{
    background-color: #FFFFFF;
    alternate-background-color: #FAFAF8;
    gridline-color: #EEEFEC;
    border: 1px solid {LINE};
    border-radius: 3px;
    selection-background-color: #EEF2F6;
    selection-color: #1F2328;
}}
QHeaderView::section {{
    background-color: #F7F7F4;
    color: #3C4043;
    padding: 8px 8px;
    border: none;
    border-bottom: 1px solid {LINE};
    font-size: 12px;
    font-weight: 600;
}}
QTableWidget::item {{ padding: 4px; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent;
    color: #5F6368;
    padding: 9px 16px;
    border-bottom: 2px solid transparent;
    font-weight: 500;
}}
QTabBar::tab:selected {{ color: #111111; border-bottom: 2px solid {NAVY}; }}

QProgressBar {{
    background-color: #E8E9E5;
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{ background-color: {NAVY}; border-radius: 3px; }}

QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; border: none; }}
QScrollBar::handle:vertical {{ background: #C4C7C2; border-radius: 4px; min-height: 36px; margin: 2px; }}
QScrollBar::handle:vertical:hover {{ background: #9A9E99; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 0; border: none; }}
QScrollBar::handle:horizontal {{ background: #C4C7C2; border-radius: 4px; min-width: 36px; margin: 2px; }}
QScrollBar::handle:horizontal:hover {{ background: #9A9E99; }}
QScrollBar::add-line, QScrollBar::sub-line {{ background: transparent; border: none; width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QMenuBar {{ background-color: {HEADER}; color: #C9CCD1; }}
QMenuBar::item:selected {{ background: #3A3F46; color: #FFFFFF; }}
QMenu {{
    background-color: #FFFFFF;
    border: 1px solid {LINE};
    padding: 4px;
}}
QMenu::item {{ padding: 7px 24px; color: #1F2328; }}
QMenu::item:selected {{ background: #EEF2F6; }}
QMenu::item:disabled {{ color: #5F6368; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 4px 8px; }}
QToolTip {{
    background-color: {HEADER};
    color: #FFFFFF;
    border: 1px solid {HEADER};
    padding: 5px 7px;
}}
QMessageBox, QDialog {{ background-color: #FFFFFF; }}

/* ---- the design kit (ui4.kit) ------------------------------------------- */
QWidget#DesignPage, QWidget#PageBody, QWidget#PageHeadBar {{ background: {PAGE}; }}
QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget > QWidget {{ background: {PAGE}; }}
QWidget#DesignPage QLabel#PageTitle {{ font-size: 21px; font-weight: 600; color: #1F2328; }}
QLabel#PageCaption {{ font-family: {MONO}; font-size: 13px; color: #5F6368; }}
QLabel#PageNote {{ font-size: 13px; color: #5F6368; }}
QFrame#Card, QFrame#StatStrip {{
    background-color: #FFFFFF;
    border: 1px solid {LINE};
    border-radius: 3px;
}}
QFrame#CardHead {{ background: #FFFFFF; border: none; border-bottom: 1px solid {HAIR}; }}
QFrame#TabHead {{ background: #FFFFFF; border: none; border-bottom: 1px solid {HAIR}; }}
QLabel#CardTitle {{ font-size: 15px; font-weight: 600; color: #1F2328; }}
QLabel#CardCaption {{ font-size: 13px; color: #6B6F74; }}
QPushButton#Link {{
    background: transparent; border: none; padding: 0; color: {NAVY};
    text-decoration: underline; font-weight: 400;
}}
QPushButton#Link:hover {{ color: #0F2F4D; background: transparent; }}

QFrame#StatCell {{ background: transparent; border: none; }}
QFrame#StatCell[first="false"] {{ border-left: 1px solid {HAIR}; }}
QLabel#StatLabel {{ font-size: 13px; color: #5F6368; }}
QLabel#StatValue {{ font-size: 23px; font-weight: 600; color: #1F2328; }}
QLabel#StatValue[alert="true"] {{ color: #B3261E; }}
QLabel#StatMono {{ font-family: {MONO}; font-size: 15px; font-weight: 600; color: #1F2328; }}
QLabel#StatAlert {{ font-size: 16px; color: #B3261E; }}
QLabel#StatNote {{ font-size: 13px; color: #5F6368; }}

QLabel#Pill {{
    border-radius: 2px; padding: 2px 7px; font-size: 12px; font-weight: 600;
    border: 1px solid #D2D3CE; background: #EEEEEB; color: #45484D;
}}
QLabel#Pill[tone="ok"] {{ background: #EAF4EC; color: #1E7B34; border-color: #A8D5B2; }}
QLabel#Pill[tone="warn"] {{ background: #FEF6E0; color: #7A5200; border-color: #EBCB82; }}
QLabel#Pill[tone="fail"] {{ background: #FCEDEC; color: #B3261E; border-color: #E7B0AB; }}
QLabel#Pill[tone="info"] {{ background: #E8EFF7; color: {NAVY}; border-color: #A9C1D9; }}
QLabel#Pill[tone="dark"] {{ background: #1E2327; color: #FFFFFF; border-color: #1E2327; }}
QLabel#Pill[tone="engine"] {{
    background: #FFFFFF; color: #3C4043; border: 1px dashed #9A9E99;
    font-family: {MONO}; font-weight: 500;
}}

QTableWidget#DesignTable {{
    background: #FFFFFF; border: none; border-radius: 0;
    selection-background-color: #E6EEF7; selection-color: #1F2328;
    alternate-background-color: #FFFFFF;
}}
QTableWidget#DesignTable::item {{ border-bottom: 1px solid {HAIR}; padding: 0 8px; }}
QTableWidget#DesignTable::item:selected {{ background: #E6EEF7; color: #1F2328; }}
QTableWidget#DesignTable QHeaderView::section {{
    background: #F7F7F5; color: #3C4043; border: none; border-bottom: 1px solid {HAIR};
    padding: 8px 10px; font-size: 13px; font-weight: 600;
}}

QFrame#Segmented {{ background: transparent; border: none; }}
QPushButton#Seg {{
    border: 1px solid #C4C7C2; border-radius: 0; padding: 7px 14px; margin-left: -1px;
    background: #FFFFFF; color: #1F2328; font-weight: 400;
}}
QPushButton#Seg[edge="first"] {{ border-top-left-radius: 3px; border-bottom-left-radius: 3px; margin-left: 0; }}
QPushButton#Seg[edge="last"] {{ border-top-right-radius: 3px; border-bottom-right-radius: 3px; }}
QPushButton#Seg:checked {{ background: #1B1F22; border-color: #1B1F22; color: #FFFFFF; }}
QPushButton#Seg:hover:!checked {{ background: #F4F5F2; color: #1F2328; }}

QTabBar#Underline {{ background: transparent; }}
QTabBar#Underline::tab {{
    background: transparent; color: #3C4043; padding: 10px 14px 8px 14px; margin: 0 2px;
    border: none; border-bottom: 2px solid transparent; font-size: 14px; font-weight: 500;
}}
QTabBar#Underline::tab:selected {{ color: #111111; border-bottom: 2px solid {NAVY}; font-weight: 600; }}
QTabBar#Underline::tab:hover:!selected {{ color: #111111; }}

QTabBar#Filters {{ background: transparent; }}
QTabBar#Filters::tab {{
    background: transparent; color: #3C4043; padding: 10px 7px 8px 7px; margin: 0 1px;
    border: none; border-bottom: 2px solid transparent; font-size: 13px; font-weight: 500;
}}
QTabBar#Filters::tab:selected {{ color: #111111; border-bottom: 2px solid {NAVY}; font-weight: 600; }}
QLabel#KvKey {{ color: #5F6368; font-size: 14px; }}
QLabel#FieldLabel {{ font-size: 13px; font-weight: 600; color: #1F2328; }}
QFrame#DropZone {{ border: 1px dashed #9A9E99; border-radius: 3px; background: #FAFAF8; }}
QFrame#DropZone[hover="true"] {{ border-color: {NAVY}; background: #EEF3F8; }}
QLabel#DropTitle {{ font-size: 14px; font-weight: 600; color: #1F2328; }}
QLabel#DropNote {{ font-size: 13px; color: #5F6368; }}
QLabel#DetailName {{ font-family: {MONO}; font-size: 13px; font-weight: 600; color: #1F2328; }}
QLabel#MonoCaption {{
    font-family: {MONO}; font-size: 12px; color: #3C4043; background: #F7F7F5;
    border-bottom: 1px solid {HAIR}; padding: 8px 12px;
}}
QPlainTextEdit#Reader, QPlainTextEdit#ReaderMono {{
    border: none; background: #FFFFFF; padding: 10px 12px; font-size: 14px;
}}
QPlainTextEdit#ReaderMono {{ font-family: {MONO}; font-size: 12px; }}
QLabel#LegendText {{ font-size: 13px; color: #3C4043; }}
QFrame#CaseHead {{ background: #FFFFFF; border: none; border-bottom: 1px solid {HAIR}; }}
QScrollArea#CaseScroll {{ background: #FFFFFF; border: none; }}
QScrollArea#CaseScroll > QWidget > QWidget {{ background: #FFFFFF; }}
QLabel#CaseRef {{ font-family: {MONO}; font-size: 19px; font-weight: 600; color: #1F2328; }}
QLabel#CaseMeta {{ font-size: 13px; color: #5F6368; }}
QFrame#Assessment {{ border: 1px dashed #9A9E99; border-radius: 2px; background: #FAFBFA; }}
QLabel#MonoTitle {{ font-family: {MONO}; font-size: 12px; font-weight: 600; letter-spacing: 1px; color: #3C4043; }}
QLabel#MonoTag {{
    font-family: {MONO}; font-size: 12px; color: #3C4043; background: #EEEEEB;
    border-radius: 2px; padding: 2px 6px;
}}
QLabel#Explanation {{ font-size: 15px; color: #1F2328; }}
QLabel#FactName {{ font-size: 13px; font-weight: 600; color: #1F2328; }}
QLabel#FactValue {{ font-size: 14px; color: #1F2328; }}
QLabel#FactMono {{ font-family: {MONO}; font-size: 13px; color: #1F2328; }}
QLabel#SubTitle {{ font-size: 15px; font-weight: 600; color: #1F2328; }}
QLabel#ReportText {{
    font-size: 15px; color: #1F2328; background: #FFFFFF; border: 1px solid {LINE};
    border-radius: 3px; padding: 12px 14px;
}}
QFrame#CueTable {{ border: 1px solid {LINE}; border-radius: 2px; background: #FFFFFF; }}
QLabel#CueQuote {{ font-size: 14px; color: #1F2328; background: #FDF8EA; padding: 7px 10px; border-bottom: 1px solid {HAIR}; }}
QLabel#CueKind {{ font-size: 13px; color: #5F6368; padding: 7px 10px; border-bottom: 1px solid {HAIR}; }}
QLabel#Steps {{ font-size: 14px; color: #1F2328; }}
QLabel#Hint {{ font-size: 13px; color: #5F6368; }}
QFrame#DecisionBar {{ background: #FFFFFF; border: none; border-top: 2px solid #1E2327; }}
QPushButton#Danger {{
    background-color: #A8261C; border: 1px solid #A8261C; color: #FFFFFF;
    padding: 10px 18px; font-size: 15px; font-weight: 600;
}}
QPushButton#Danger:hover {{ background-color: #8E1F17; color: #FFFFFF; }}
QPushButton#Danger:disabled {{ background-color: #D9A3A0; border-color: #D9A3A0; color: #FFFFFF; }}
QPushButton#DecisionButton {{ padding: 10px 18px; font-size: 15px; font-weight: 600; }}
QLabel#Insight {{ font-size: 13px; color: #5F6368; padding: 8px 12px; border-top: 1px solid {HAIR}; }}
QLabel#BigAvatar {{
    background: #3A3F46; color: #FFFFFF; border-radius: 25px; font-size: 17px; font-weight: 600;
}}
QLabel#ProfileName {{ font-size: 19px; font-weight: 600; color: #1F2328; }}
QLabel#InlineValue {{ font-size: 14px; font-weight: 600; color: #1F2328; }}
QLabel#InlineMono {{ font-family: {MONO}; font-size: 14px; font-weight: 600; color: #1F2328; }}
QLabel#SideTitle {{ font-size: 14px; font-weight: 600; color: #1F2328; }}
QLabel#SideText {{ font-size: 14px; color: #1F2328; }}
QLabel#SideFaint {{ font-size: 14px; color: #6B6F74; }}
QLabel#TriggerCount {{ font-size: 14px; font-weight: 600; color: #1F2328; }}
QLabel#KvValue {{ color: #1F2328; font-size: 14px; }}
QLabel#KvMono {{ color: #1F2328; font-size: 14px; font-family: {MONO}; }}

QFrame#Alert {{ border: 1px solid #D2D3CE; border-radius: 3px; background: #F7F7F5; }}
QFrame#Alert[tone="critical"] {{ background: #FCEDEC; border-color: #E7B0AB; }}
QFrame#Alert[tone="warn"] {{ background: #FEF9EC; border-color: #EBCB82; }}
QFrame#Alert QLabel#AlertText {{ font-size: 14px; color: #1F2328; }}
QLabel#AlertMark {{ font-size: 14px; color: #3C4043; }}
QLabel#AlertMark[tone="critical"] {{ color: #B3261E; }}
QLabel#AlertMark[tone="warn"] {{ color: #9A6A00; }}

QFrame#TimelineRow {{ border: none; border-bottom: 1px solid {HAIR}; background: transparent; }}
QLabel#TimelineTime {{ font-family: {MONO}; font-size: 13px; color: #5F6368; }}
QLabel#TimelineText {{ font-size: 14px; color: #1F2328; }}
QLabel#TimelineSub {{ font-size: 13px; color: #5F6368; }}

/* ---- Compliance Action Items: the calendar ------------------------------ */
QWidget#CalendarGrid {{ background: #FFFFFF; }}
QLabel#CalendarPeriod {{ font-size: 18px; font-weight: 600; color: #1F2328; }}
QLabel#WeekdayName {{ font-weight: 600; color: #3C4043; padding: 4px 0; }}
QPushButton#CalendarStep {{ padding: 7px 12px; min-width: 18px; }}
QPushButton#ModeButton:checked {{ background-color: #E6EDF4; border-color: {NAVY}; color: {NAVY}; }}
QFrame#DayCell {{ background-color: #EDEEEA; border: 1px solid #EDEEEA; border-radius: 2px; }}
QFrame#DayCell[outside="true"] {{ background-color: #F6F6F3; border-color: #F6F6F3; }}
QFrame#DayCell[selected="true"] {{ background-color: #D9DBD6; border-color: #C4C7C2; }}
QFrame#DayCell[today="true"] {{ border: 2px solid {NAVY}; }}
QFrame#DayCell QLabel#DayNumber {{ color: #5F6368; font-size: 12px; }}
QFrame#DayCell[today="true"] QLabel#DayNumber {{ color: {NAVY}; font-weight: 700; }}
QFrame#DayCell QFrame#ActionChip {{
    background-color: #FFFFFF;
    border: 1px solid #E1E3DE;
    border-left: 3px solid #FFFFFF;
    border-radius: 2px;
}}
QFrame#DayCell QFrame#ActionChip:hover {{ border-color: {NAVY}; }}
QFrame#DayCell QFrame#ActionChip[kind="corrective"] {{ border-left: 3px solid {NAVY}; }}
QFrame#DayCell QFrame#ActionChip[state="overdue"] {{ border-left: 3px solid #C0392B; }}
QFrame#DayCell QFrame#ActionChip[state="done"] {{ background-color: #F7F7F5; }}
QFrame#ActionChip QLabel#ChipText {{ color: #1F2328; font-size: 13px; }}
QFrame#ActionChip[state="done"] QLabel#ChipText {{ color: #8A8F95; }}
QFrame#DayCell QPushButton#MoreLink {{
    background: transparent;
    border: none;
    color: #3C4043;
    padding: 2px 6px;
}}
QFrame#DayCell QPushButton#MoreLink:hover {{ color: {NAVY}; text-decoration: underline; }}
"""


FONT_FILES = ("IBMPlexSans-Regular.ttf", "IBMPlexSans-Italic.ttf", "IBMPlexSans-Medium.ttf",
              "IBMPlexSans-SemiBold.ttf", "IBMPlexSans-Bold.ttf", "IBMPlexMono-Regular.ttf",
              "IBMPlexMono-Medium.ttf", "IBMPlexMono-SemiBold.ttf")
_fonts_loaded = False


def load_fonts() -> bool:
    """Register the bundled IBM Plex faces (SIL OFL), once, if Qt is running.

    Bundled so the design reads the same on a workstation that has never had
    Plex installed; without them the platform's own sans stands in.
    """
    global _fonts_loaded
    if _fonts_loaded:
        return True
    import os

    from PyQt6.QtGui import QFontDatabase, QGuiApplication

    if QGuiApplication.instance() is None:
        return False
    folder = os.path.join(_ASSETS, "fonts")
    loaded = [QFontDatabase.addApplicationFont(os.path.join(folder, name))
              for name in FONT_FILES if os.path.isfile(os.path.join(folder, name))]
    _fonts_loaded = any(index >= 0 for index in loaded)
    return _fonts_loaded


def prepare() -> None:
    """Repoint the shared colours and the typography, before a window is built."""
    from .theme import apply_look, apply_palette

    load_fonts()

    apply_palette(PALETTE)
    apply_look(table_headers_upper=False, nav_upper=False, nav_numbered=False,
               nav_icons=True)


def dress(window: "QMainWindow") -> None:
    """Put the style sheet on a built window. The shell hides the old chrome."""
    window.setStyleSheet(STYLESHEET)
