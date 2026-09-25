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
           "FONT", "MONO", "prepare", "dress"]

NAME = "Two workspaces"

#: The sheets' own colours.
HEADER = "#1F2328"           # the title row
NAVY = "#1F4E79"             # HSE: selected tab, review badge, primary action
AMBER = "#C98A1B"            # Administration: rule, tag, selected tab
CREAM = "#F7F3EA"            # Administration: the tab row
PAGE = "#F2F2EE"             # the page behind the cards
LINE = "#D9DBD6"             # hairlines

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
QWidget {{
    background-color: {PAGE};
    color: {_C["TEXT"]};
    font-family: {FONT};
    font-size: 13px;
}}
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
QLabel#PageTitle {{ font-size: 21px; font-weight: 600; }}
QLabel#SectionTitle {{ font-size: 15px; font-weight: 600; color: #1F2328; }}
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

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
    background-color: #FFFFFF;
    border: 1px solid #C4C7C2;
    border-radius: 3px;
    padding: 7px 9px;
    color: #1F2328;
    selection-background-color: {NAVY};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {NAVY};
}}
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
"""


def prepare() -> None:
    """Repoint the shared colours and the typography, before a window is built."""
    from .theme import apply_look, apply_palette

    apply_palette(PALETTE)
    apply_look(table_headers_upper=False, nav_upper=False, nav_numbered=False,
               nav_icons=True)


def dress(window: "QMainWindow") -> None:
    """Put the style sheet on a built window. The shell hides the old chrome."""
    window.setStyleSheet(STYLESHEET)
