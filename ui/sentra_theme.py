"""SENTRA - the revamped application design (sentra.py).

The same pages as the two-workspace build, dressed as the Revamp Application
UI draws them: a near-black title row over a dark tab row with a white
underline, Tailwind's greys on a warm page (#F0EFEB), navy #1E3A5F for
anything pressable, Inter for text and JetBrains Mono for anything a machine
wrote. Status pills are the revamp's tinted blue, green, amber and red; risk
bars are red at critical, amber from 50, grey below.

Built on :mod:`ui.workspace_theme` - its style sheet recoloured, then the
revamp's own rules on top - so a page added to the two-workspace build is
dressed here without a second style sheet to keep in step.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from . import workspace_theme
from .theme import ASSETS as _ASSETS

if TYPE_CHECKING:  # pragma: no cover
    from PyQt6.QtWidgets import QMainWindow

__all__ = ["PALETTE", "STYLESHEET", "NAME", "NAVY", "PAGE", "HEADER", "TABS", "FONT", "MONO",
           "CATEGORY_COLOURS", "load_fonts", "prepare", "dress"]

NAME = "SENTRA"

NAVY = "#1E3A5F"
NAVY_DARK = "#16305A"
PAGE = "#F0EFEB"
HEADER = "#18181B"
TABS = "#222226"
AMBER = "#CD881A"
FONT = '"Inter", "Segoe UI", "DejaVu Sans", Arial, sans-serif'
MONO = '"JetBrains Mono", "Consolas", "DejaVu Sans Mono", monospace'

#: Tailwind's scale, as the revamp uses it.
GRAY = {50: "#F9FAFB", 100: "#F3F4F6", 200: "#E5E7EB", 300: "#D1D5DB", 400: "#9CA3AF",
        500: "#6B7280", 600: "#4B5563", 700: "#374151", 800: "#1F2937", 900: "#111827"}

#: Action-item categories as the revamp colours them.
CATEGORY_COLOURS = {
    "Inspection": "#3B82F6", "Permit to work": "#10B981", "Energy isolation": "#F97316",
    "Training": "#8B5CF6", "Environmental": "#14B8A6", "Maintenance": "#F59E0B",
    "Corrective action": "#EF4444",
}

PALETTE = dict(workspace_theme.PALETTE, APP=PAGE, HEADER=HEADER, ACCENT=NAVY,
               ACCENT_DIM=NAVY_DARK, BORDER=GRAY[200], BORDER_SOFT=GRAY[100], TEXT=GRAY[900],
               TEXT_DIM=GRAY[500], TEXT_FAINT=GRAY[400], INFO=NAVY, RAIL_ACCENT=NAVY)

#: The two-workspace sheet's colours and faces, and what the revamp uses instead.
_RECOLOUR = (
    ("#F1F2ED", PAGE), ("#1E4F7A", NAVY), ("#173A5A", NAVY_DARK), ("#1E2327", HEADER),
    ("#DCDDD8", GRAY[200]), ("#E9EAE6", GRAY[100]), ("#1F2328", GRAY[900]),
    ("#5F6368", GRAY[500]), ("#3C4043", GRAY[700]), ("#8A8F95", GRAY[400]),
    ("#6B6F74", GRAY[400]), ("#C4C7C2", GRAY[300]), ("#9A9E99", GRAY[400]),
    ("#F7F7F5", GRAY[50]), ("#FAFAF8", GRAY[50]), ("#E6EEF7", "#EFF6FF"),
    ("#EEF2F6", "#EFF6FF"), ("#A8261C", "#DC2626"), ("#8E1F17", "#B91C1C"),
    ('"IBM Plex Sans"', '"Inter"'), ('"IBM Plex Mono"', '"JetBrains Mono"'),
)


def _recolour(sheet: str) -> str:
    for old, new in _RECOLOUR:
        sheet = sheet.replace(old, new).replace(old.lower(), new)
    return sheet


G = GRAY
OVERRIDES = f"""
/* ==== the revamp, over the two-workspace sheet ============================= */
QWidget {{ font-family: {FONT}; font-size: 13px; color: {G[900]}; }}
QMainWindow {{ background-color: {PAGE}; }}

/* the title row */
QFrame#WorkspaceHeader {{ background-color: {HEADER}; }}
QFrame#WorkspaceHeader[workspace="admin"] {{ border-top: 3px solid {AMBER}; }}
QFrame#WorkspaceHeader QLabel#OrgName {{ font-size: 12px; font-weight: 500; color: #FFFFFF; }}
QFrame#WorkspaceHeader QLabel#OrgPlace {{ font-size: 10px; color: {G[300]}; }}
QLabel#Wordmark {{ font-size: 15px; font-weight: 700; letter-spacing: 5px; color: #FFFFFF; }}
QFrame#WorkspaceHeader QLabel#WorkspaceTag {{
    font-family: {FONT}; font-size: 9px; font-weight: 500; letter-spacing: 1.5px;
    color: rgba(255,255,255,0.6); border: 1px solid rgba(255,255,255,0.3); border-radius: 0;
    padding: 2px 8px;
}}
QFrame#WorkspaceHeader QLabel#WorkspaceTag[workspace="admin"] {{ color: #F2B84B; border-color: {AMBER}; }}
QFrame#WorkspaceHeader QLabel#ProjectCode {{ font-family: {MONO}; font-size: 12px; color: {G[400]}; }}
QFrame#WorkspaceHeader QLabel#Avatar {{ background-color: #475569; }}
QFrame#WorkspaceHeader QLabel#UserName {{ font-size: 12px; font-weight: 500; }}
QFrame#WorkspaceHeader QLabel#UserRole {{ font-size: 10px; color: {G[400]}; }}
QFrame#WorkspaceHeader QLabel#OilLogo {{ background: transparent; padding: 0; }}
QFrame#WorkspaceHeader QLabel#Badge {{ background-color: #EF4444; }}

/* the tab row: dark, a white underline under the page you are on */
QFrame#TabRow {{ background-color: {TABS}; border-bottom: 1px solid rgba(255,255,255,0.10); }}
QFrame#TabRow[workspace="admin"] {{ background-color: {TABS}; }}
QPushButton#WorkspaceTab {{
    color: {G[400]}; font-size: 14px; font-weight: 400; padding: 10px 16px 9px 16px;
    border-bottom: 2px solid transparent;
}}
QPushButton#WorkspaceTab:hover {{ color: {G[200]}; border-bottom-color: transparent; }}
QPushButton#WorkspaceTab:checked {{ color: #FFFFFF; font-weight: 500; border-bottom: 2px solid #FFFFFF; }}
QFrame#TabRow[workspace="admin"] QPushButton#WorkspaceTab:checked {{ border-bottom: 2px solid {AMBER}; }}
QFrame#TabRow QLabel#TabBadge {{
    background-color: {NAVY}; color: #FFFFFF; border-radius: 2px; font-family: {MONO};
    font-size: 10px; font-weight: 500; padding: 1px 5px;
}}
QFrame#TabRow QLabel#TabNote {{ font-family: {MONO}; font-size: 10px; color: {G[500]}; }}

/* pages */
QWidget#DesignPage QLabel#PageTitle {{ font-size: 20px; font-weight: 600; color: {G[900]}; }}
QLabel#PageCaption {{ font-family: {MONO}; font-size: 11px; color: {G[400]}; }}
QLabel#PageNote {{ font-size: 12px; color: {G[500]}; }}
QFrame#Card, QFrame#StatStrip {{ background: #FFFFFF; border: 1px solid {G[200]}; border-radius: 4px; }}
QFrame#CardHead, QFrame#TabHead {{ border-bottom: 1px solid {G[100]}; }}
QLabel#CardTitle {{ font-size: 14px; font-weight: 600; color: {G[900]}; }}
QLabel#CardCaption {{ font-size: 11px; color: {G[400]}; }}
QPushButton#Link {{ color: {NAVY}; text-decoration: none; font-size: 12px; }}
QPushButton#Link:hover {{ text-decoration: underline; }}

QFrame#StatCell[first="false"] {{ border-left: 1px solid {G[200]}; }}
QLabel#StatLabel {{ font-size: 11px; color: {G[500]}; }}
QLabel#StatValue {{ font-size: 30px; font-weight: 700; color: {G[900]}; }}
QLabel#StatValue[alert="true"] {{ color: {G[900]}; }}
QLabel#StatAlert {{ font-size: 14px; color: #EF4444; }}
QLabel#StatNote {{ font-size: 11px; color: {G[400]}; }}
QLabel#StatMono {{ font-family: {MONO}; font-size: 14px; font-weight: 600; }}

QLabel#Pill {{ border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 500; }}
QLabel#Pill[tone="ok"] {{ background: #F0FDF4; color: #15803D; border: 1px solid #BBF7D0; }}
QLabel#Pill[tone="warn"] {{ background: #FFFBEB; color: #B45309; border: 1px solid #FDE68A; }}
QLabel#Pill[tone="fail"] {{ background: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }}
QLabel#Pill[tone="info"] {{ background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; }}
QLabel#Pill[tone="grey"] {{ background: {G[100]}; color: {G[600]}; border: 1px solid {G[100]}; }}
QLabel#Pill[tone="dark"] {{ background: #F0FDF4; color: #166534; border: 1px solid #BBF7D0; }}
QLabel#Pill[tone="engine"] {{
    background: {G[800]}; color: #FFFFFF; border: 1px solid {G[800]}; font-family: {FONT};
}}
QLabel#Pill[tone="engine-sif"] {{ background: {NAVY}; color: #FFFFFF; border: 1px solid {NAVY}; }}

QTableWidget#DesignTable {{ font-size: 12px; selection-background-color: #EFF6FF; }}
QTableWidget#DesignTable::item {{ border-bottom: 1px solid {G[50]}; }}
QTableWidget#DesignTable::item:selected {{ background: #EFF6FF; color: {G[900]}; }}
QTableWidget#DesignTable QHeaderView::section {{
    background: #FFFFFF; color: {G[500]}; font-size: 12px; font-weight: 500;
    border-bottom: 1px solid {G[100]}; padding: 8px 12px;
}}

QPushButton {{ border: 1px solid {G[300]}; border-radius: 4px; padding: 5px 12px; font-size: 12px; font-weight: 400; }}
QPushButton:hover {{ background-color: {G[50]}; border-color: {G[300]}; color: {G[900]}; }}
QPushButton#Primary {{ background-color: {NAVY}; border-color: {NAVY}; color: #FFFFFF; font-weight: 500; }}
QPushButton#Primary:hover {{ background-color: {NAVY_DARK}; border-color: {NAVY_DARK}; color: #FFFFFF; }}
QPushButton#Danger {{ background-color: #DC2626; border-color: #DC2626; border-radius: 4px; font-size: 14px; font-weight: 500; }}
QPushButton#Danger:hover {{ background-color: #B91C1C; }}
QPushButton#DecisionButton {{ font-size: 14px; font-weight: 400; padding: 8px 20px; }}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QDateEdit, QSpinBox {{
    border: 1px solid {G[300]}; border-radius: 4px; padding: 5px 8px; font-size: 12px;
}}
QPushButton#Seg {{ border: 1px solid {G[300]}; font-size: 12px; padding: 6px 12px; }}
QPushButton#Seg:checked {{ background: {NAVY}; border-color: {NAVY}; color: #FFFFFF; }}
QCheckBox::indicator:checked {{ background-color: {NAVY}; border-color: {NAVY}; }}
QTabBar#Underline::tab {{ font-size: 13px; font-weight: 400; color: {G[500]}; }}
QTabBar#Underline::tab:selected {{ color: {G[900]}; border-bottom: 2px solid {G[800]}; font-weight: 500; }}

QFrame#Alert {{ border: none; border-radius: 0; background: #FFFFFF; border-bottom: 1px solid {G[100]}; }}
QFrame#Alert[tone="critical"] {{ background: #FEF2F2; border: none; border-bottom: 1px solid {G[100]}; }}
QFrame#Alert[tone="warn"] {{ background: #FFFBEB; border: none; border-bottom: 1px solid {G[100]}; }}
QLabel#AlertMark[tone="critical"] {{ color: #EF4444; font-size: 11px; }}
QLabel#AlertMark[tone="warn"] {{ color: #F59E0B; font-size: 11px; }}
QLabel#AlertMark {{ color: {G[400]}; font-size: 11px; }}
QFrame#Alert QLabel#AlertText {{ font-size: 13px; color: {G[700]}; }}

QFrame#DropZone {{ border: 2px dashed {G[200]}; border-radius: 4px; background: #FFFFFF; }}
QLabel#DropTitle {{ font-size: 13px; font-weight: 500; color: {G[700]}; }}
QLabel#DropNote {{ font-size: 11px; color: {G[400]}; }}
QFrame#DecisionBar {{ border-top: 1px solid {G[200]}; }}
QFrame#Assessment {{ border: 1px solid {G[200]}; border-radius: 4px; background: #FFFFFF; }}
QLabel#MonoTitle {{ font-size: 11px; color: {G[600]}; }}
QLabel#ReportText {{ background: {G[50]}; border: 1px solid {G[200]}; border-radius: 4px; font-size: 14px; color: {G[700]}; }}
QLabel#FactName {{ font-size: 12px; font-weight: 400; color: {G[400]}; }}
QLabel#FactValue {{ font-size: 12px; font-weight: 600; color: {G[900]}; }}
QLabel#CaseRef {{ font-size: 18px; font-weight: 700; }}
QLabel#CaseMeta {{ font-size: 12px; color: {G[500]}; }}
QLabel#Explanation {{ font-size: 14px; color: {G[800]}; }}
QLabel#TriggerCount {{ font-size: 14px; font-weight: 600; }}
QLabel#TimelineTime {{ font-size: 11px; color: {G[400]}; }}
QLabel#TimelineText {{ font-size: 12px; color: {G[700]}; }}
QLabel#TimelineSub {{ font-size: 10px; color: {G[400]}; }}
QFrame#TimelineRow {{ border-bottom: none; }}
QLabel#KvKey {{ font-size: 14px; color: {G[400]}; }}
QLabel#KvValue {{ font-size: 14px; font-weight: 500; color: {G[800]}; }}
QLabel#BigAvatar {{ background: #475569; border-radius: 25px; font-weight: 700; }}
QListWidget#SettingsNav::item:selected {{ background: {G[50]}; border-left: 3px solid {AMBER}; }}
QScrollBar:vertical {{ width: 6px; }}
QScrollBar::handle:vertical {{ background: {G[300]}; border-radius: 3px; }}
QScrollBar:horizontal {{ height: 6px; }}

/* action items: chips in their category's colour */
QFrame#DayCell {{ background: #FFFFFF; border: none; border-right: 1px solid {G[100]}; border-bottom: 1px solid {G[100]}; border-radius: 0; }}
QFrame#DayCell[outside="true"] {{ background: {G[50]}; }}
QFrame#DayCell[selected="true"] {{ background: #F5F8FC; }}
QFrame#DayCell[today="true"] {{ border: none; border-right: 1px solid {G[100]}; border-bottom: 1px solid {G[100]}; }}
QFrame#DayCell QLabel#DayNumber {{ font-size: 12px; font-weight: 500; color: {G[600]}; padding: 2px 6px; }}
QFrame#DayCell[today="true"] QLabel#DayNumber {{ background: {NAVY}; color: #FFFFFF; border-radius: 11px; }}
QFrame#DayCell QFrame#ActionChip {{ border: none; border-radius: 3px; background: {G[500]}; }}
QFrame#ActionChip QLabel#ChipText {{ color: #FFFFFF; font-size: 10px; }}
QFrame#DayCell QFrame#ActionChip[state="overdue"] {{ border: 1px solid #EF4444; }}
QFrame#DayCell QFrame#ActionChip[state="done"] {{ background: {G[300]}; }}
QFrame#ActionChip[state="done"] QLabel#ChipText {{ color: {G[600]}; }}
QFrame#DayCell QPushButton#MoreLink {{ color: {G[400]}; font-size: 10px; }}
QLabel#WeekdayName {{ font-size: 11px; font-weight: 500; color: {G[500]}; }}
QWidget#CalendarGrid {{ background: #FFFFFF; }}
QFrame#UpcomingRow {{ border-bottom: 1px solid {G[50]}; }}
QLabel#UpcomingMonth {{ font-family: {MONO}; font-size: 10px; color: {G[400]}; }}
QLabel#UpcomingDay {{ font-size: 18px; font-weight: 700; color: {G[800]}; }}
QLabel#UpcomingDayToday {{ font-size: 18px; font-weight: 700; color: {NAVY}; }}
QLabel#UpcomingTitle {{ font-size: 12px; font-weight: 500; color: {G[800]}; }}
QLabel#UpcomingSub {{ font-size: 10px; color: {G[400]}; }}
QLabel#LegendTitle {{ font-size: 12px; font-weight: 600; color: {G[600]}; }}
QPushButton#CategoryButton {{ font-size: 12px; color: {G[700]}; }}
QPushButton#Seg {{ border-radius: 4px; margin-left: 0; }}
QFrame#SummaryStrip {{ background: {G[50]}; border: 1px solid {G[100]}; }}
QFrame#SummaryStrip QLabel#StatValue {{ font-size: 16px; }}
QFrame#SummaryStrip QLabel#StatLabel {{ font-size: 12px; color: {G[400]}; }}

/* sign-in */
QFrame#LoginForm {{ background: #FFFFFF; }}
QLabel#FormOrg {{ font-size: 14px; font-weight: 700; color: {G[900]}; }}
QLabel#FormDept {{ font-size: 12px; color: {G[500]}; }}
QLabel#FormWordmark {{ font-size: 30px; font-weight: 700; letter-spacing: 4px; color: {G[900]}; }}
QLabel#FormTag {{ font-size: 12px; letter-spacing: 1.5px; color: {G[400]}; }}
QLabel#FormFoot {{ font-family: {MONO}; font-size: 10px; color: {G[400]}; }}
QFrame#LoginForm QLabel#FieldLabel {{ font-size: 12px; font-weight: 400; color: {G[500]}; }}
QFrame#LoginForm QLineEdit {{ padding: 8px 10px; font-size: 13px; min-height: 22px; }}
QFrame#LoginForm QLabel#LoginNote {{ font-size: 11px; color: {G[400]}; }}
QFrame#LoginForm QLabel#LoginTitle {{ font-size: 20px; }}
QPushButton#LoginPrimary {{ background: {NAVY}; border-color: {NAVY}; border-radius: 4px; font-size: 13px; padding: 9px 16px; }}
QPushButton#LoginPrimary:hover {{ background: {NAVY_DARK}; }}
QPushButton#ShowPassword {{ background: {G[50]}; color: {G[400]}; font-size: 12px; }}
QLabel#GradientWordmark {{ font-size: 60px; font-weight: 700; letter-spacing: 9px; color: #FFFFFF; }}
QLabel#GradientTag {{ font-size: 12px; letter-spacing: 1.5px; color: {G[400]}; }}
QLabel#GradientLine {{ font-size: 18px; font-weight: 300; color: rgba(255,255,255,0.8); letter-spacing: 0.5px; }}
QToolButton#LLMButton {{
    font-family: {MONO}; font-size: 12px; color: #E4E4E7; background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.14); border-radius: 14px; padding: 2px 10px 2px 8px;
}}
QToolButton#LLMButton:hover {{ background: rgba(255,255,255,0.12); }}
QToolButton#LLMButton[state="off"] {{ color: {G[400]}; }}
QToolButton#LLMButton[state="offline"] {{ border-color: rgba(239,68,68,0.55); }}
QToolButton#LLMButton::menu-button {{ border: none; width: 16px; }}
QToolButton#LLMButton::menu-arrow {{ width: 8px; height: 8px; }}
/* pop-ups in the revamp's greys (the rules above keep them white everywhere) */
QMenu, QFrame#WorkspaceHeader QMenu, QFrame#TabRow QMenu, QFrame#Card QMenu,
QWidget#DesignPage QMenu {{
    background-color: #FFFFFF; color: {G[900]}; border: 1px solid {G[200]};
    border-radius: 6px; padding: 4px;
}}
QMenu::item, QFrame#WorkspaceHeader QMenu::item {{
    background: transparent; color: {G[900]}; font-size: 13px; padding: 8px 28px 8px 14px;
    border-radius: 4px;
}}
QMenu::item:selected, QFrame#WorkspaceHeader QMenu::item:selected {{
    background-color: #EFF6FF; color: {NAVY};
}}
QMenu::item:disabled, QFrame#WorkspaceHeader QMenu::item:disabled {{ color: {G[500]}; }}
QMenu::separator, QFrame#WorkspaceHeader QMenu::separator {{
    height: 1px; background: {G[200]}; margin: 4px 6px;
}}
QComboBox QAbstractItemView, QFrame#WorkspaceHeader QComboBox QAbstractItemView {{
    background-color: #FFFFFF; color: {G[900]}; border: 1px solid {G[200]};
    selection-background-color: #EFF6FF; selection-color: {NAVY};
}}
QComboBox QAbstractItemView::item:hover {{ background-color: #EFF6FF; }}
QLabel#GradientStatus {{
    font-family: {MONO}; font-size: 12px; color: rgba(255,255,255,0.7);
    background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.20);
    border-radius: 16px; padding: 7px 20px;
}}
""" + "".join(
    f'QFrame#DayCell QFrame#ActionChip[category="{name}"] {{{{ background: {colour}; }}}}\n'
    .replace("{{", "{").replace("}}", "}") for name, colour in CATEGORY_COLOURS.items())

STYLESHEET = _recolour(workspace_theme.STYLESHEET) + OVERRIDES

FONT_FILES = ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf", "Inter-Bold.ttf",
              "JetBrainsMono-Regular.ttf", "JetBrainsMono-Medium.ttf",
              "JetBrainsMono-SemiBold.ttf", "JetBrainsMono-Bold.ttf")
_fonts_loaded = False


def load_fonts() -> bool:
    """Register the bundled Inter and JetBrains Mono (SIL OFL), once."""
    global _fonts_loaded
    if _fonts_loaded:
        return True
    from PyQt6.QtGui import QFontDatabase, QGuiApplication

    if QGuiApplication.instance() is None:
        return False
    folder = os.path.join(_ASSETS, "fonts")
    loaded = [QFontDatabase.addApplicationFont(os.path.join(folder, name))
              for name in FONT_FILES if os.path.isfile(os.path.join(folder, name))]
    _fonts_loaded = any(index >= 0 for index in loaded)
    return _fonts_loaded


def prepare() -> None:
    """Colours, faces and the drawn parts' tokens, before a window is built."""
    from ui4 import kit

    from .theme import apply_look, apply_palette

    from ui4 import hotspots

    load_fonts()
    workspace_theme.load_fonts()
    hotspots.SCHEME.clear()
    hotspots.SCHEME.update(hotspots.SCHEME_DEFAULT, mode="opacity", base="#6B7280",
                           selected=NAVY, ring=NAVY)
    apply_palette(PALETTE)
    apply_look(table_headers_upper=False, nav_upper=False, nav_numbered=False, nav_icons=True)
    kit.configure(
        TEXT=GRAY[900], MUTED=GRAY[500], FAINT=GRAY[400], LINE=GRAY[200], HAIR=GRAY[100],
        NAVY=NAVY, RED="#DC2626", BAR=NAVY, TRACK=GRAY[200], MONO_FAMILY="JetBrains Mono",
        STAT_STACKED=True, RISK_NUMBER_RED=True, HEAD_STACKED=True,
        RISK_STEPS=[(85, "#DC2626"), (50, "#F59E0B"), (0, GRAY[400])],
        TONES={"ok": ("#F0FDF4", "#15803D", "#BBF7D0"),
               "warn": ("#FFFBEB", "#B45309", "#FDE68A"),
               "fail": ("#FEF2F2", "#B91C1C", "#FECACA"),
               "info": ("#EFF6FF", "#1D4ED8", "#BFDBFE"),
               "grey": (GRAY[100], GRAY[600], GRAY[100]),
               "dark": ("#F0FDF4", "#166534", "#BBF7D0"),
               "engine": (GRAY[800], "#FFFFFF", GRAY[800]),
               "engine-sif": (NAVY, "#FFFFFF", NAVY)})


def dress(window: "QMainWindow") -> None:
    window.setStyleSheet(STYLESHEET)
