@echo off
REM Builds dist\LimiTools.exe (GUI), dist\LimiToolsCLI.exe (console)
REM and, if Inno Setup 6 is installed, dist\LimiToolsSetup.exe (installer).
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv || goto :fail
.venv\Scripts\python -m pip install -q -r requirements.txt pyinstaller || goto :fail
REM RoValra for the Received trades tab: pinned, checksum-verified, view-only patched (see the script).
.venv\Scripts\python tools\fetch_rovalra.py || goto :fail
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --icon assets\icon.ico --add-data "assets\icon.ico;assets" --add-data "assets\icon.png;assets" --add-data "assets\fonts;assets\fonts" --add-data "vendor\rovalra;vendor\rovalra" --hidden-import pystray._win32 --collect-all webview --hidden-import clr --name LimiTools gui.py || goto :fail
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --console ^
    --icon assets\icon.ico --name LimiToolsCLI main.py || goto :fail

set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
for /f "delims=" %%v in ('.venv\Scripts\python -c "import roliposter; print(roliposter.__version__)"') do set "VER=%%v"
if exist "%ISCC%" (
    "%ISCC%" /Q /DAppVersion=%VER% installer.iss || goto :fail
    echo Built: dist\LimiToolsSetup.exe ^(share this one^)
) else (
    echo Inno Setup 6 not found; skipped the installer. Install it with: winget install JRSoftware.InnoSetup
)
echo Built: dist\LimiTools.exe and dist\LimiToolsCLI.exe
exit /b 0
:fail
echo Build failed.
exit /b 1
