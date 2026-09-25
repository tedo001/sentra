"""The Flowbite skin: the console in the Flowbite admin dashboard's design.

Transcribed from ``tedo001/sample-ui-1`` - Themesberg's Flowbite Admin
Dashboard (MIT) - by reading the Tailwind classes its layouts actually use, so
each value below can be traced to a class in the template:

``page``        ``bg-gray-50``                        #F9FAFB
``sidebar``     ``bg-white border-r border-gray-200``  white, #E5E7EB edge
``nav item``    ``text-gray-900 rounded-lg p-2 hover:bg-gray-100``; the item
                you are on is ``bg-gray-100``, not a coloured pill
``nav icon``    ``text-gray-500 group-hover:text-gray-900``
``card``        ``bg-white border border-gray-200 rounded-lg``
``button``      ``bg-primary-700 hover:bg-primary-800 rounded-lg font-medium``
``secondary``   ``bg-white border-gray-200 hover:bg-gray-100 hover:text-primary-700``
``input``       ``bg-gray-50 border-gray-300 rounded-lg focus:border-primary-500``
``table head``  ``bg-gray-50 text-xs font-medium text-gray-500 uppercase``
``tabs``        ``text-primary-600 border-b-2 border-primary-600`` when selected
``font``        Inter, then the platform's own sans

The primary scale is the template's ``tailwind.config.js``; the status colours
are Flowbite's own palette (green #0E9F6E, red #E02424, yellow #C27803), which
reads on white where the dark skins' glowing ambers and teals would not.

The template's shadows (``shadow-sm``) are not transcribed: a Qt style sheet
cannot draw a shadow, so the card border does the separating on its own - which
is the template's look in its bordered variant anyway.

The header keeps the mark, the avatar and the search box hidden, as in the
other skins - they were asked out of the console earlier, and a template's
navbar is not a reason to bring them back. :func:`dress` is where to change it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .theme import ASSETS as _ASSETS

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PyQt6.QtWidgets import QMainWindow

__all__ = ["PALETTE", "STYLESHEET", "NAME", "prepare", "dress"]

NAME = "Flowbite admin"

#: Tailwind gray scale, as Flowbite uses it.
GRAY = {50: "#F9FAFB", 100: "#F3F4F6", 200: "#E5E7EB", 300: "#D1D5DB", 400: "#9CA3AF",
        500: "#6B7280", 600: "#4B5563", 700: "#374151", 800: "#1F2937", 900: "#111827"}
#: The template's primary scale (tailwind.config.js).
PRIMARY = {50: "#eff6ff", 100: "#dbeafe", 200: "#bfdbfe", 300: "#93c5fd", 500: "#3b82f6",
           600: "#2563eb", 700: "#1d4ed8", 800: "#1e40af"}

PALETTE = {
    "APP": GRAY[50],
    "SIDEBAR": "#FFFFFF",
    "HEADER": "#FFFFFF",
    "PANEL": "#FFFFFF",
    "PANEL_ALT": GRAY[50],
    "CARD": "#FFFFFF",
    "BORDER": GRAY[200],
    "BORDER_SOFT": GRAY[100],

    "TEXT": GRAY[900],
    "TEXT_DIM": GRAY[500],
    "TEXT_FAINT": GRAY[400],

    "BRAND": "#E02424",
    "ACCENT": PRIMARY[700],
    "ACCENT_SOFT": PRIMARY[500],
    "ACCENT_DIM": PRIMARY[800],
    "BLUE": "#1C64F2",
    "PURPLE": "#7E3AF2",
    # The selected nav item is grey-100 with grey-900 text, so its icon is
    # grey-900 too - the template's group-hover:text-gray-900.
    "ICON_ON": GRAY[900],

    "SCROLL_TRACK": GRAY[50],
    "SCROLL_THUMB": GRAY[300],
    "SCROLL_THUMB_HOVER": GRAY[400],

    # Flowbite's own status colours - chosen for white, not for near-black.
    "DANGER": "#E02424",
    "WARN": "#C27803",
    "OK": "#0E9F6E",
    "INFO": "#1C64F2",

    # The safety card at the foot of the rail, as the template's primary-50
    # call-out cards are drawn.
    "RAIL_WASH": PRIMARY[50],
    "RAIL_LINE": PRIMARY[200],
    "RAIL_ACCENT": PRIMARY[700],
}

_C = PALETTE
_FONT = ('"Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Roboto", '
         '"Helvetica Neue", "DejaVu Sans", Arial, sans-serif')
_MONO = '"ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "DejaVu Sans Mono", monospace'

STYLESHEET = f"""
QWidget {{
    background-color: {GRAY[50]};
    color: {GRAY[900]};
    font-family: {_FONT};
    font-size: 13px;
}}
QLabel {{ background: transparent; border: none; }}

/* sidebar: bg-white border-r border-gray-200 */
QFrame#Sidebar {{
    background-color: #FFFFFF;
    border-right: 1px solid {GRAY[200]};
}}
/* The rail's list and rows are plain widgets; left alone they paint the page's
   grey-50 inside the white rail. */
QFrame#Sidebar QWidget, QFrame#Sidebar QScrollArea {{ background: transparent; }}
QFrame#Sidebar QScrollArea {{ border: none; }}
QPushButton#Nav {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px 10px;
    margin: 1px 10px;
    text-align: left;
    font-size: 14px;
    font-weight: 400;
    color: {GRAY[900]};
}}
QPushButton#Nav:hover {{ background-color: {GRAY[100]}; }}
QPushButton#Nav:checked {{
    background-color: {GRAY[100]};
    font-weight: 600;
}}

/* navbar: bg-white border-b border-gray-200 */
QFrame#Header {{
    background-color: #FFFFFF;
    border-bottom: 1px solid {GRAY[200]};
}}
QWidget#HeaderBrand {{ background: transparent; }}
QWidget#HeaderBrand QLabel#BrandName {{
    font-size: 19px;
    font-weight: 600;
    color: {GRAY[900]};
}}
QSplitter#Shell::handle {{ background-color: {GRAY[200]}; }}
QSplitter#Shell::handle:hover {{ background-color: {PRIMARY[500]}; }}
/* The CRUD pages' white title block with a rule under it. */
QFrame#PageHead {{
    background-color: #FFFFFF;
    border-bottom: 1px solid {GRAY[200]};
    padding-bottom: 12px;
}}
QFrame#Footer {{
    background-color: #FFFFFF;
    border-top: 1px solid {GRAY[200]};
}}
/* card: bg-white border border-gray-200 rounded-lg */
QFrame#Panel, QFrame#Card, QFrame#Tile {{
    background-color: #FFFFFF;
    border: 1px solid {GRAY[200]};
    border-radius: 8px;
}}

QLabel#AppTitle {{ font-size: 24px; font-weight: 700; }}
QLabel#AppSubtitle {{ font-size: 13px; color: {GRAY[500]}; }}
QLabel#BrandName {{ font-size: 14px; font-weight: 600; color: {GRAY[900]}; }}
QLabel#BrandSub {{ font-size: 8px; color: {GRAY[400]}; }}
/* text-xl sm:text-2xl font-semibold text-gray-900 */
QLabel#PageTitle {{ font-size: 21px; font-weight: 600; }}
QLabel#SectionTitle {{ font-size: 16px; font-weight: 600; color: {GRAY[900]}; }}
/* The small uppercase captions over a KPI or a field block. */
QLabel#Caption {{
    font-size: 10.5px;
    font-weight: 500;
    color: {GRAY[500]};
    letter-spacing: 0.6px;
}}
QLabel#Muted {{ color: {GRAY[500]}; }}
QLabel#Faint {{ color: {GRAY[400]}; font-size: 12px; }}
/* text-2xl font-bold leading-none sm:text-3xl */
QLabel#KpiValue {{ font-size: 28px; font-weight: 700; }}
QLabel#KpiUnit {{ font-size: 12px; color: {GRAY[500]}; }}

/* py-2.5 px-5 text-sm font-medium bg-white border border-gray-200 rounded-lg */
QPushButton {{
    background-color: #FFFFFF;
    border: 1px solid {GRAY[200]};
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
    color: {GRAY[900]};
}}
QPushButton:hover {{
    background-color: {GRAY[100]};
    color: {PRIMARY[700]};
}}
QPushButton:pressed {{ background-color: {GRAY[200]}; }}
QPushButton:disabled {{ color: {GRAY[400]}; background-color: {GRAY[50]}; }}
/* text-white bg-primary-700 hover:bg-primary-800 rounded-lg */
QPushButton#Primary {{
    background-color: {PRIMARY[700]};
    border: 1px solid {PRIMARY[700]};
    color: #FFFFFF;
}}
QPushButton#Primary:hover {{
    background-color: {PRIMARY[800]};
    border-color: {PRIMARY[800]};
    color: #FFFFFF;
}}
QPushButton#Primary:disabled {{
    background-color: {PRIMARY[300]};
    border-color: {PRIMARY[300]};
    color: #FFFFFF;
}}
/* Flowbite's red button: text-white bg-red-700 hover:bg-red-800 */
QPushButton#Warning {{
    background-color: #C81E1E;
    border: 1px solid #C81E1E;
    color: #FFFFFF;
}}
QPushButton#Warning:hover {{ background-color: #9B1C1C; border-color: #9B1C1C; color: #FFFFFF; }}

/* bg-gray-50 border border-gray-300 text-gray-900 rounded-lg p-2.5 */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {GRAY[50]};
    border: 1px solid {GRAY[300]};
    border-radius: 8px;
    padding: 8px 10px;
    color: {GRAY[900]};
    selection-background-color: {PRIMARY[500]};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {PRIMARY[500]};
}}
QComboBox {{
    background-color: {GRAY[50]};
    border: 1px solid {GRAY[300]};
    border-radius: 8px;
    padding: 7px 10px;
    color: {GRAY[900]};
}}
QComboBox:focus {{ border: 1px solid {PRIMARY[500]}; }}
QComboBox QAbstractItemView {{
    background-color: #FFFFFF;
    border: 1px solid {GRAY[200]};
    selection-background-color: {GRAY[100]};
    selection-color: {GRAY[900]};
}}
QCheckBox {{ spacing: 8px; background: transparent; }}
/* w-4 h-4 border-gray-300 rounded bg-gray-50; checked primary-600. The
   indicator has to be drawn here: any style sheet rule on QCheckBox puts Qt's
   own drawing aside, and an unstyled one then draws nothing at all. */
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {GRAY[300]};
    border-radius: 4px;
    background-color: {GRAY[50]};
}}
QCheckBox::indicator:hover {{ border-color: {PRIMARY[500]}; }}
QCheckBox::indicator:checked {{
    background-color: {PRIMARY[600]};
    border-color: {PRIMARY[600]};
    image: url({_ASSETS}/check.svg);
}}
QCheckBox::indicator:disabled {{ background-color: {GRAY[100]}; border-color: {GRAY[200]}; }}

/* bg-white divide-y divide-gray-200, hover:bg-gray-100 */
QTableWidget {{
    background-color: #FFFFFF;
    alternate-background-color: #FFFFFF;
    gridline-color: {GRAY[200]};
    border: 1px solid {GRAY[200]};
    border-radius: 8px;
    selection-background-color: {GRAY[100]};
    selection-color: {GRAY[900]};
}}
/* p-4 text-xs font-medium text-gray-500 uppercase bg-gray-50. The capitals
   come from apply_look(): a style sheet has no text-transform. */
QHeaderView::section {{
    background-color: {GRAY[50]};
    color: {GRAY[500]};
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid {GRAY[200]};
    font-size: 11px;
    font-weight: 500;
}}
QTableWidget::item {{ padding: 4px; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent;
    color: {GRAY[500]};
    padding: 10px 16px;
    border-bottom: 2px solid transparent;
    font-weight: 500;
}}
QTabBar::tab:hover {{ color: {GRAY[600]}; border-bottom-color: {GRAY[300]}; }}
QTabBar::tab:selected {{
    color: {PRIMARY[600]};
    border-bottom: 2px solid {PRIMARY[600]};
}}

/* w-full bg-gray-200 rounded-full h-2.5; the bar bg-primary-600 */
QProgressBar {{
    background-color: {GRAY[200]};
    border: none;
    border-radius: 5px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{ background-color: {PRIMARY[600]}; border-radius: 5px; }}

QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; border: none; }}
QScrollBar::handle:vertical {{
    background: {GRAY[300]};
    border-radius: 4px;
    min-height: 36px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{ background: {GRAY[400]}; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 0; border: none; }}
QScrollBar::handle:horizontal {{
    background: {GRAY[300]};
    border-radius: 4px;
    min-width: 36px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{ background: {GRAY[400]}; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    background: transparent; border: none; width: 0px; height: 0px;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QStatusBar {{ background-color: #FFFFFF; color: {GRAY[500]}; }}
QMenuBar {{ background-color: #FFFFFF; color: {GRAY[700]}; }}
QMenuBar::item:selected {{ background: {GRAY[100]}; color: {GRAY[900]}; }}
/* Flowbite dropdown: bg-white divide-y rounded-lg shadow */
QMenu {{
    background-color: #FFFFFF;
    border: 1px solid {GRAY[200]};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{ padding: 7px 22px; border-radius: 6px; color: {GRAY[700]}; }}
QMenu::item:selected {{ background: {GRAY[100]}; color: {GRAY[900]}; }}
/* Flowbite's dark tooltip: bg-gray-900 text-white rounded-lg */
QToolTip {{
    background-color: {GRAY[900]};
    color: #FFFFFF;
    border: 1px solid {GRAY[900]};
    border-radius: 6px;
    padding: 6px 8px;
}}
QMessageBox, QDialog {{ background-color: #FFFFFF; }}
"""


def prepare() -> None:
    """Repoint the shared colours and the typography, before a window is built.

    Flowbite sets table headings in capitals and its sidebar in sentence case
    with an icon on every item - so capitals for the tables only, and the rail
    keeps its drawn icons. Every skin states all of the switches, so none is
    inherited from whichever skin was prepared before.
    """
    from .theme import apply_look, apply_palette

    apply_palette(PALETTE)
    apply_look(table_headers_upper=True, nav_upper=False, nav_numbered=False,
               nav_icons=True)


def dress(window: "QMainWindow") -> None:
    """Put the skin on a built window: the style sheet and the quiet header."""
    window.setStyleSheet(STYLESHEET)
    header = getattr(window, "header", None)
    for name in ("mark", "avatar", "search"):
        widget = getattr(header, name, None)
        if widget is not None:
            widget.hide()
