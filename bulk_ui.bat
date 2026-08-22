@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Bulk Publisher UI
set "PYTHONIOENCODING=utf-8"

echo ============================================================
echo    BULK PUBLISHER UI  -  http://127.0.0.1:8700
echo    classics  : Gutendex text -^> A5 PDF + cover + LibriVox
echo    generated : local AI story + cover + audio + PDF
echo ============================================================
echo.

rem ---------------- locate Python (prefer the full SD venv) ----------------
set "PY="
if exist "D:\stable-diffusion-webui\venv\Scripts\python.exe" set "PY=D:\stable-diffusion-webui\venv\Scripts\python.exe"
if not defined PY ( if exist "D:\Writer\.venv\Scripts\python.exe" set "PY=D:\Writer\.venv\Scripts\python.exe" )
if not defined PY ( where py >nul 2>nul && set "PY=py -3" )
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY ( echo [ERROR] Python not found. & pause & exit /b 1 )
echo Using Python: %PY%

rem ---------------- keep caches on D: ----------------
if not exist "D:\pipcache" mkdir "D:\pipcache" >nul 2>nul
set "PIP_CACHE_DIR=D:\pipcache"
set "HF_HOME=D:\hf_cache"
set "HF_HUB_CACHE=D:\hf_cache\hub"
set "HF_HUB_DISABLE_SYMLINKS=1"

rem ---------------- deps check (flask etc.) ----------------
%PY% -c "import flask, requests, PIL, reportlab" >nul 2>nul
if errorlevel 1 (
    echo Installing UI dependencies (flask)...
    %PY% -m pip install flask
    if errorlevel 1 ( echo [ERROR] pip install failed. & pause & exit /b 1 )
)

cd /d "%~dp0"
echo.
echo Starting the UI. Open http://127.0.0.1:8700 in your browser.
echo Close this window (or press Ctrl+C) to stop the server.
echo.
%PY% -m bulk.ui_server
pause
