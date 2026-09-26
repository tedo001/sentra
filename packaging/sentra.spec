# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for SENTRA (sentra.py) - the two-workspace console.

Build from the repository root (Windows makes a Windows .exe; PyInstaller
cannot cross-compile):

    pyinstaller packaging\\sentra.spec --noconfirm --clean

Output: ``dist\\SENTRA\\SENTRA.exe`` and the folder it runs from. Then
``packaging\\sentra_installer.iss`` turns that folder into one setup file.
``packaging\\build_sentra.bat`` does both, in order.

Two variants, chosen with ``SIF_BUILD_VARIANT``:

``full`` (default)
    Everything: sentence-transformers, XGBoost, MLflow and PaddleOCR are
    bundled, so every page does what it says with nothing to install later.
    Several gigabytes.

``slim``
    The interface, the rule engine, PDF text-layer reading, the SQL and
    vector database, backups and the LLM client. Around 250 MB. The Engines
    page says which analysers are absent.

Ollama and gemma2:latest are never bundled: Ollama is its own service, and
SENTRA finds it over HTTP (see sentra_after_install.txt).

This spec sits beside ``sif_console.spec`` (the single-window console the
v2.0.0 release ships) and changes nothing in it or in the release workflow.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

VARIANT = os.environ.get("SIF_BUILD_VARIANT", "full").lower()
APP_NAME = "SENTRA"
EXECUTABLE = "SENTRA"
ENTRY = "sentra.py"

ROOT = os.path.abspath(os.getcwd())
ICON = os.path.join(ROOT, "ui", "assets", "sentra.ico")

# Our own packages, module by module: themes, pages and workers are imported
# inside functions, and a module reached only that way is one PyInstaller can miss.
hidden = ["main", "main2", "main4", "main5", "app", "app4", "sentra",
          # SQLAlchemy chooses its dialect from the URL at run time.
          "sqlalchemy.dialects.sqlite", "sqlalchemy.dialects.sqlite.pysqlite"]
for package in ("sif", "ui", "ui2", "ui4", "ui5"):
    hidden += [package] + collect_submodules(package)

datas = [
    # Fonts (SIL OFL, with their licences), the OIL emblem, scroll arrows.
    (os.path.join(ROOT, "ui", "assets"), os.path.join("ui", "assets")),
    (os.path.join(ROOT, "samples"), "samples"),
    (os.path.join(ROOT, "sample_reports.csv"), "."),
]
binaries = []

# Whole packages whose resources an import graph does not reveal.
ALWAYS = ["cryptography", "sqlalchemy"]
OPTIONAL = ["torch", "transformers", "sentence_transformers", "xgboost", "sklearn",
            "scipy", "mlflow", "paddle", "paddleocr", "pandas"]

for package in ALWAYS + ([] if VARIANT == "slim" else OPTIONAL):
    try:
        package_datas, package_binaries, package_hidden = collect_all(package)
    except Exception as exc:                     # not installed on this machine
        print(f"[sentra.spec] {package} not collected: {exc}")
        continue
    datas += package_datas
    binaries += package_binaries
    hidden += package_hidden

excludes = ["matplotlib", "tkinter"] + (OPTIONAL if VARIANT == "slim" else [])

a = Analysis(
    [os.path.join(ROOT, ENTRY)],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hidden)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=EXECUTABLE,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                      # a desktop application, no terminal window
    icon=ICON if os.path.exists(ICON) else None,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=EXECUTABLE)

if sys.platform == "darwin":
    app = BUNDLE(coll, name=f"{APP_NAME}.app", icon=None,
                 bundle_identifier="in.co.oilindia.sentra",
                 info_plist={"NSHighResolutionCapable": True})
