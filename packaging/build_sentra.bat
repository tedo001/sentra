@echo off
rem Build SENTRA.exe and its setup wizard, from the repository root or anywhere.
rem
rem   packaging\build_sentra.bat          full build (every analyser bundled, several GB)
rem   packaging\build_sentra.bat slim     interface + rules + database only (~250 MB)
rem
rem Needs: 64-bit Python 3.10-3.12 on PATH, and Inno Setup 6
rem (winget install JRSoftware.InnoSetup). Output:
rem   dist\SENTRA\SENTRA.exe                      the application folder
rem   dist\installer\SENTRA-<version>-setup.exe   the setup wizard to hand out

setlocal
cd /d "%~dp0\.."

set VARIANT=%~1
if "%VARIANT%"=="" set VARIANT=full
echo === SENTRA build: %VARIANT% ===

where python >nul 2>nul
if errorlevel 1 goto :nopython

if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto :fail
call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip
if /I "%VARIANT%"=="slim" goto :slimdeps
pip install -r requirements.txt
goto :depsdone
:slimdeps
pip install -r requirements-app.txt
:depsdone
if errorlevel 1 goto :fail
pip install pyinstaller
if errorlevel 1 goto :fail

echo === 1/3 PyInstaller: dist\SENTRA\SENTRA.exe ===
set SIF_BUILD_VARIANT=%VARIANT%
pyinstaller packaging\sentra.spec --noconfirm --clean
if errorlevel 1 goto :fail

echo === 2/3 Checking the built SENTRA.exe starts (every page, the database, the theme) ===
set SENTRA_SMOKE=1
start "" /wait "dist\SENTRA\SENTRA.exe"
if errorlevel 1 goto :smokefail
set SENTRA_SMOKE=
echo SENTRA.exe starts.

echo === 3/3 Inno Setup: the setup wizard ===
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" goto :noinno

for /f "delims=" %%v in ('python -c "from sif.version import __version__; print(__version__)"') do set VER=%%v
"%ISCC%" /DAppVersion=%VER% packaging\sentra_installer.iss
if errorlevel 1 goto :fail

echo.
echo Done.
echo   Application: dist\SENTRA\SENTRA.exe
echo   Installer:   dist\installer\SENTRA-%VER%-setup.exe
exit /b 0

:nopython
echo Python was not found on PATH. Install 64-bit Python 3.11 from python.org
echo and tick "Add python.exe to PATH", then open a new terminal.
exit /b 1

:smokefail
set SENTRA_SMOKE=
echo.
echo SENTRA.exe was built but did not start. To see why, run it from a terminal:
echo     set SENTRA_SMOKE=1
echo     dist\SENTRA\SENTRA.exe
exit /b 1

:noinno
echo.
echo SENTRA.exe is built in dist\SENTRA, but Inno Setup 6 was not found, so no
echo setup wizard was made. Install it with:
echo     winget install JRSoftware.InnoSetup
echo then run this script again.
exit /b 1

:fail
echo.
echo The build stopped at the step above - read the error printed there.
exit /b 1
