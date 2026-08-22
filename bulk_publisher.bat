@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Bulk Publisher — writers-palette.com
set "PYTHONIOENCODING=utf-8"

echo ============================================================
echo    BULK PUBLISHER  -  bulk books for writers-palette.com
echo    classics  : Gutendex text -> A5 PDF + cover + LibriVox
echo    generated : local AI story + cover + audio + PDF
echo ============================================================
echo.

rem ---------------- locate Python ----------------
set "PY="
if exist "D:\stable-diffusion-webui\venv\Scripts\python.exe" set "PY=D:\stable-diffusion-webui\venv\Scripts\python.exe"
if not defined PY ( if exist "D:\Writer\.venv\Scripts\python.exe" set "PY=D:\Writer\.venv\Scripts\python.exe" )
if not defined PY ( where py >nul 2>nul && set "PY=py -3" )
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
    echo [ERROR] Python not found. Install Python 3.10+ and re-run.
    pause & exit /b 1
)
echo Using Python: %PY%

rem ---------------- keep caches on D: ----------------
if not exist "D:\pipcache" mkdir "D:\pipcache" >nul 2>nul
set "PIP_CACHE_DIR=D:\pipcache"
set "HF_HOME=D:\hf_cache"
set "HF_HUB_CACHE=D:\hf_cache\hub"
set "HF_HUB_DISABLE_SYMLINKS=1"

rem ---------------- deps check ----------------
%PY% -c "import requests, PIL, reportlab" >nul 2>nul
if errorlevel 1 (
    echo Installing required packages...
    %PY% -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 ( echo [ERROR] pip install failed. & pause & exit /b 1 )
)

rem ---------------- questions (defaults = safe) ----------------
echo.
set /p CLASSICS="How many classic books (Gutendex)? [default 3]: "
if "!CLASSICS!"=="" set CLASSICS=3
set /p GENERATED="How many AI-generated books? [default 0]: "
if "!GENERATED!"=="" set GENERATED=0

echo.
echo LibriVox audiobooks for classics:
echo   [1] link   - record the LibriVox URL on the site (safe default)
echo   [2] upload - download LibriVox chapters and publish the audiobook
echo   [3] skip   - ignore LibriVox
set /p LV="Choose (1-3) [default 1]: "
if "!LV!"=="" set LV=1
if "!LV!"=="1" set "LVFLAG=--librivox link"
if "!LV!"=="2" set "LVFLAG=--librivox upload"
if "!LV!"=="3" set "LVFLAG=--librivox skip"
if not defined LVFLAG set "LVFLAG=--librivox link"

echo.
set /p PUB="Publish to the website? [y/N]: "
set "PUBFLAG=--no-publish"
if /i "!PUB!"=="y" set "PUBFLAG="
set /p CURATED="Curated Gutenberg ids (comma-separated, empty = most popular): "
if defined CURATED set "CURFLAG=--curated !CURATED!" else set "CURFLAG="

echo.
echo ------------------------------------------------
echo  Producing %CLASSICS% classics + %GENERATED% generated books
echo  LibriVox: %LVFLAG%   Publish: %PUBFLAG%   Curated: %CURATED%
echo ------------------------------------------------
echo.

cd /d "%~dp0"
%PY% -m bulk.run_bulk --classics %CLASSICS% --generated %GENERATED% %LVFLAG% %PUBFLAG% %CURFLAG%

echo.
echo Done. See bulk/state.json and the output folder.
pause
