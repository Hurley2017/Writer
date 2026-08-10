@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title AI Story Writer

echo ============================================================
echo            AI STORY WRITER - local illustrated stories
echo ============================================================
echo.

rem ---------------- locate Python ----------------
rem Prefer the SD venv Python - it has torch + diffusers + reportlab
set "PY="
if exist "D:\stable-diffusion-webui\venv\Scripts\python.exe" set "PY=D:\stable-diffusion-webui\venv\Scripts\python.exe"
if not defined PY ( where py >nul 2>nul && set "PY=py -3" )
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY ( if exist "C:\Users\tushe\AppData\Local\Python\pythoncore-3.14-64\python.exe" set "PY=C:\Users\tushe\AppData\Local\Python\pythoncore-3.14-64\python.exe" )
if not defined PY (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org and re-run.
    pause
    exit /b 1
)
echo Using Python: %PY%

rem Redirect pip cache/temp to D: so large installs never fill the C: drive
if not exist "D:\pipcache" mkdir "D:\pipcache" >nul 2>nul
if not exist "D:\piptemp" mkdir "D:\piptemp" >nul 2>nul
set "PIP_CACHE_DIR=D:\pipcache"
set "TEMP=D:\piptemp"
set "TMP=D:\piptemp"

rem Redirect the HuggingFace model cache to D: as well
if not exist "D:\hf_cache" mkdir "D:\hf_cache" >nul 2>nul
set "HF_HOME=D:\hf_cache"
set "HF_HUB_CACHE=D:\hf_cache\hub"

rem ---------------- check dependencies ----------------
%PY% -c "import requests, PIL, reportlab, pymupdf, diffusers, torch, transformers, snac, bitsandbytes, soundfile" >nul 2>nul
if errorlevel 1 (
    echo First run detected - installing required Python packages...
    %PY% -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install Python packages.
        echo If torch is missing, install the CUDA build with:
        echo   %PY% -m pip install torch --index-url https://download.pytorch.org/whl/cu128
        pause
        exit /b 1
    )
)

echo The agent will write your story with the local LLM in LM Studio (Gemma 31B),
echo illustrate it with RealVisXL (SDXL), and narrate it with Orpheus 3B TTS
echo (dual voices: chapter titles announced by one voice, the story read by the
 echo other, chosen by the protagonist's gender) - all in one run.
echo.
echo [Environment check]
%PY% -c "import requests, PIL, reportlab, pymupdf, diffusers, torch, transformers, snac, bitsandbytes, soundfile" >nul 2>nul
if errorlevel 1 (
    echo Missing packages - install them with:
    echo   %PY% -m pip install -r "%~dp0requirements.txt"
    pause
    exit /b 1
)
echo   All required packages found.
echo.

rem ---------------- run the single interactive script ----------------
cd /d "%~dp0"
%PY% write_story.py

if errorlevel 1 (
    echo.
    echo [Something went wrong - see the messages above.]
    pause
    exit /b 1
)

echo.
echo Done! The illustrated PDF and audiobook are saved in the "output" folder.
pause
