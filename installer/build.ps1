# Build the Qirtas installer: the window (convert/app.py) frozen with
# PyInstaller, then wrapped into one setup .exe by Inno Setup.
#
#   powershell -ExecutionPolicy Bypass -File installer\build.ps1
#
# Needs, once: `.venv\Scripts\python -m pip install pyinstaller` and Inno
# Setup 6 (https://jrsoftware.org/isinfo.php). Output: installer\Output\
# Qirtas-Setup.exe. The computer it is installed on needs Microsoft Word:
# every conversion renders through it (FLAGS 26).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

& .venv\Scripts\python -m PyInstaller `
    --noconfirm --clean --windowed --onedir `
    --name Qirtas `
    --distpath installer\dist --workpath installer\build --specpath installer\build `
    --add-data "$root\convert\data;convert\data" `
    --add-data "$root\convert\ocr_windows.ps1;convert" `
    --collect-data docx `
    --hidden-import win32com.client --hidden-import pythoncom `
    --hidden-import harness.word --hidden-import harness.compare `
    convert\app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$iscc = @("$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 is not installed (ISCC.exe not found)" }
& $iscc installer\qirtas.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
Write-Host "Done: installer\Output\Qirtas-Setup.exe"
