# INNO.md - Building and updating the SENTRA installer (Inno Setup)

This is the complete procedure for turning SENTRA into a Windows setup file,
testing it, and shipping an update later. Every command is typed into the
**PyCharm terminal** (PowerShell) with the project folder open. Everything
here runs on **Windows** - PyInstaller builds for the system it runs on, so a
Linux or macOS machine cannot make the `.exe`.

```
 your code ──PyInstaller──▶ dist\SENTRA\SENTRA.exe ──Inno Setup──▶ dist\installer\SENTRA-2.0.0-setup.exe
            (makes the app)      (a folder that runs)                 (the one file you hand out)
```

---

## 1. What you get

| File | What it is |
| --- | --- |
| `dist\SENTRA\SENTRA.exe` | The application, with everything it needs in the same folder. |
| `dist\installer\SENTRA-<version>-setup.exe` | The setup wizard: this is the file you give to people. |

The setup wizard runs in this order: **Welcome → What is installed and where
data lives → Install folder → Start-menu folder → Desktop shortcut → Installing
→ What to do next (Ollama and `gemma2:latest`) → Finish**, with *Start SENTRA*
ticked. It adds Start-menu entries for SENTRA, SENTRA (presentation size), the
after-install notes, and Uninstall.

SENTRA keeps its data - accounts, audit trail, review decisions, action items,
the SQL database, sealed secrets, settings, logs - in
`%APPDATA%\SIF Insight Console`, **never** in the program folder. Installing an
update or uninstalling does not touch that folder.

---

## 2. One-time setup of the build PC

Install these once. Open a **new** PyCharm terminal afterwards so it sees them.

| Tool | How | Check |
| --- | --- | --- |
| Python 3.11 (64-bit) | <https://www.python.org/downloads/> - tick **Add python.exe to PATH** | `python --version` |
| Git | <https://git-scm.com/download/win> | `git --version` |
| Inno Setup 6 | `winget install JRSoftware.InnoSetup` (or <https://jrsoftware.org/isdl.php>) | `& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /?` |

Get the code (skip if you already have it open in PyCharm):

```powershell
git clone https://github.com/tedo001/sentra.git
cd sentra
git checkout tedo
```

---

## 3. Build the installer - one command

```powershell
git pull origin tedo
.\packaging\build_sentra.bat
```

That is all. The script:

1. creates `.venv` and installs everything in `requirements.txt` plus PyInstaller;
2. builds `dist\SENTRA\SENTRA.exe` from `packaging\sentra.spec`;
3. **starts the built SENTRA.exe once, with no sign-in, to prove every page
   loads** - it stops here if anything is missing;
4. compiles `packaging\sentra_installer.iss` into
   `dist\installer\SENTRA-<version>-setup.exe`.

Choose the size:

| Command | Includes | Size |
| --- | --- | --- |
| `.\packaging\build_sentra.bat` | Everything: the semantic encoder, XGBoost, MLflow, PaddleOCR | several GB |
| `.\packaging\build_sentra.bat slim` | The interface, the rule engine, PDF text, the SQL/vector database, backups, the LLM client | about 250 MB |

The first full build downloads a few gigabytes of Python packages and takes a
while; later builds reuse `.venv`.

---

## 4. Build it step by step (what the script does)

Use this when you want to see each step, or when something fails.

```powershell
# 1. A virtual environment, once
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if PowerShell refuses: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 2. Dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt       # or requirements-app.txt for the slim build
pip install pyinstaller

# 3. Check SENTRA runs from source
python sentra.py

# 4. Build SENTRA.exe
$env:SIF_BUILD_VARIANT = "full"       # or "slim"
pyinstaller packaging\sentra.spec --noconfirm --clean

# 5. Check the built exe starts (opens every page, closes, exit code 0)
$env:SENTRA_SMOKE = "1"; Start-Process dist\SENTRA\SENTRA.exe -Wait; Remove-Item Env:SENTRA_SMOKE

# 6. Make the setup wizard
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" packaging\sentra_installer.iss
```

**With the Inno Setup window instead of step 6:** open Inno Setup, *File →
Open* `packaging\sentra_installer.iss`, then *Build → Compile* (Ctrl+F9). The
output is the same file in `dist\installer\`. Step 4 must have run first -
Inno Setup only packages the folder PyInstaller made, it does not compile
Python.

---

## 5. Test the installer before handing it out

1. Run `dist\installer\SENTRA-<version>-setup.exe` and click through the wizard.
2. SENTRA starts at the end. On the sign-in page:
   * **Admin Login** → username `admin`, password `sih165` → opens **Administration** (Engines).
   * **HSE Login** → username `hse`, password `sih2026165` → opens the **HSE workspace** (Home).
   * Signing in with the HSE account through Admin Login (or the other way round) is refused.
3. Load `samples\near_miss_reports.csv` from the install folder on **Ingest**,
   check the Dashboard, Risk Hotspots map and HSE Review.
4. *Settings → Apps → SENTRA → Uninstall* removes the program; your data in
   `%APPDATA%\SIF Insight Console` stays for the next install.

> **Change the two built-in passwords before real use.** Sign in, open
> *Profile → Change password*. Once a password is changed, the sign-in page
> stops showing it.

---

## 6. Updating the app (shipping a new version)

Do this every time you change SENTRA and want people to get the change.

### 6.1 Make and check the change

```powershell
git pull origin tedo
# ...edit the code...
$env:QT_QPA_PLATFORM = "offscreen"; $env:SIF_ENCODER = "hashing"
python -m pytest -q                   # every test must pass
Remove-Item Env:QT_QPA_PLATFORM, Env:SIF_ENCODER
python sentra.py                      # look at it yourself
```

### 6.2 Raise the version number

The version must go **up** (2.0.0 → 2.0.1 for a fix, 2.1.0 for new features,
3.0.0 for a big change). One command writes it everywhere it is needed -
`sif\version.py`, `packaging\installer.iss` and `packaging\sentra_installer.iss`:

```powershell
python packaging\stamp_version.py v2.1.0
```

### 6.3 Rebuild

```powershell
.\packaging\build_sentra.bat
```

The result is `dist\installer\SENTRA-2.1.0-setup.exe`.

### 6.4 Install the update on a PC

Run the new setup file on the PC that has the old version. It **upgrades in
place**:

* it finds the existing SENTRA (same `AppId` in the script) and installs into
  the same folder;
* it offers to close SENTRA if it is running (`CloseApplications=yes`);
* it keeps every account, decision, audit entry, action item, database and
  setting, because those live in `%APPDATA%\SIF Insight Console`, not in the
  program folder;
* *Settings → Apps* then shows the new version number.

No uninstall is needed first.

### 6.5 Record the release

```powershell
git add -A
git commit -m "SENTRA 2.1.0: <what changed>"
git tag -a v2.1.0 -m "SENTRA 2.1.0"
git push origin tedo --tags
```

Optionally attach `SENTRA-2.1.0-setup.exe` to a GitHub release (*Releases →
Draft a new release → choose the tag → attach the file*).

### 6.6 Rules that keep updates working

| Never | Because |
| --- | --- |
| change `AppId` in `sentra_installer.iss` | a new AppId installs a second, separate SENTRA instead of updating the first |
| ship the same or a lower version | Windows and the update check cannot tell the new build from the old one |
| put data files into the program folder | they would be overwritten by the next update; SENTRA writes to `%APPDATA%` for this reason |

---

## 7. Changing what the installer says or does

All in `packaging\sentra_installer.iss`:

| To change | Edit |
| --- | --- |
| Name shown in the wizard and Apps list | `#define AppName "SENTRA"` |
| Publisher | `#define AppPublisher "Oil India Limited"` |
| Default install folder | `DefaultDirName={autopf}\SENTRA` |
| Installer icon | `SetupIconFile=..\ui\assets\sentra.ico` (the app's icon is set in `sentra.spec`) |
| Page before installing | `packaging\sentra_before_install.txt` |
| Page after installing | `packaging\sentra_after_install.txt` |
| Desktop shortcut offered unticked | in `[Tasks]`, add `Flags: unchecked` to the `desktopicon` line (it is ticked now) |
| Start-menu entries | the `[Icons]` section |
| Output file name | `OutputBaseFilename=SENTRA-{#AppVersion}-setup` |

After editing, run step 6 of section 4 (or *Build → Compile* in Inno Setup).

---

## 8. Installing on many PCs (IT staff)

```powershell
# Silent install, no questions, default folder
SENTRA-2.1.0-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART

# Into a chosen folder, for all users
SENTRA-2.1.0-setup.exe /VERYSILENT /ALLUSERS /DIR="C:\Programs\SENTRA"

# Silent uninstall
"C:\Program Files\SENTRA\unins000.exe" /VERYSILENT
```

---

## 9. Troubleshooting

| What you see | What to do |
| --- | --- |
| `python` is not recognised | Reinstall Python with *Add python.exe to PATH*, open a new terminal. |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again. |
| `Inno Setup 6 was not found` | `winget install JRSoftware.InnoSetup`, open a new terminal, run the script again. |
| The script stops at *Checking the built SENTRA.exe starts* | Run `$env:SENTRA_SMOKE="1"; .\dist\SENTRA\SENTRA.exe` in the terminal to read the error; usually a package missing from `.venv` - `pip install -r requirements.txt` and rebuild. |
| `ModuleNotFoundError` when the installed app starts | Add the module to `hidden` in `packaging\sentra.spec`, rebuild. |
| The antivirus quarantines `SENTRA.exe` | Unsigned new executables are sometimes flagged; add an exclusion for the build folder, or sign the exe and the installer with a code-signing certificate (`signtool sign`). |
| The installer is very large | Build with `.\packaging\build_sentra.bat slim`. |
| After updating, the old version still shows | The AppId was changed, or the version was not raised - see section 6.6. |
| The gemma2:latest button stays red | Install Ollama (<https://ollama.com/download>), run `ollama pull gemma2:latest`, press the button. |

---

## 10. Files involved

| File | Role |
| --- | --- |
| `packaging\build_sentra.bat` | The one-command build (sections 3 and 6.3). |
| `packaging\sentra.spec` | What PyInstaller puts into `dist\SENTRA`. |
| `packaging\sentra_installer.iss` | The Inno Setup script: the wizard, shortcuts, version. |
| `packaging\sentra_before_install.txt`, `sentra_after_install.txt` | The two information pages of the wizard. |
| `packaging\stamp_version.py` | Writes the version into the code and both setup scripts. |
| `ui\assets\sentra.ico` | The application and installer icon (the OIL emblem). |
| `sif\version.py` | The version the running app reports. |
