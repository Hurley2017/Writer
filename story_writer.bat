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

rem ---------------- check dependencies ----------------
%PY% -c "import requests, PIL, reportlab, pymupdf, diffusers, torch" >nul 2>nul
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

echo The agent will write your story with the local LLM in LM Studio,
echo illustrate it, and build a PDF in the same format as your sample book.
echo.
echo [Environment check]
%PY% -m src.pipeline --check
echo.

rem ---------------- gather story preferences ----------------
echo.
echo ============================================================
echo    TELL ME WHAT KIND OF STORY YOU WANT
echo ============================================================
echo.
set /p GENRE="Genre (sci-fi, romance, fantasy, thriller, mystery, horror, drama, adventure...): "
if "%GENRE%"=="" set "GENRE=general fiction"
echo.
set /p TOPIC="Premise or elements you want in the story (empty = I invent it): "
set /p TONE="Tone (dark, light, humorous, epic, emotional...): "
echo.
echo Length:  [1] Short   [2] Medium   [3] Long
set /p LENCHOICE="Choose (1-3, default 2): "
if "%LENCHOICE%"=="1" ( set "LEN=short" ) else if "%LENCHOICE%"=="3" ( set "LEN=long" ) else ( set "LEN=medium" )
echo.
set /p TITLE="Book title (empty = I invent one): "
set /p AUTHOR="Author name for the PDF (optional): "
echo.
echo [1] Defaults (auto-pick LM model + auto-detect image backend)
echo [2] Advanced (choose LM model and image backend)
set /p ADV="Choose (1-2, default 1): "
set "EXTRA="
if "%ADV%"=="2" (
    echo.
    echo Available LM models in LM Studio:
    %PY% -c "import requests,json; m=requests.get('http://localhost:1234/v1/models',timeout=5).json().get('data',[]); [print('   ['+str(i+1)+'] '+x['id']) for i,x in enumerate(m)]" 2>nul
    echo   [0] Auto (pick the largest loaded model)
    set /p MCH="Choose LM model (0-Auto, or type any model id): "
    if not "!MCH!"=="0" if not "!MCH!"=="" set "EXTRA=!EXTRA! --model !MCH!"
    echo.
    echo Image backend:
    echo   [1] Auto (embedded diffusers if a model is set, else server, else placeholder)
    echo   [2] Embedded Stable Diffusion (diffusers, standalone - recommended)
    echo   [3] Stable Diffusion WebUI (local server on port 7860)
    echo   [4] ComfyUI (local server on port 8188)
    echo   [5] OpenAI images / DALL-E (needs API key in config.json)
    echo   [6] Placeholder images (no model needed)
    set /p BCH="Choose (1-6, default 1): "
    if "!BCH!"=="2" set "EXTRA=!EXTRA! --backend diffusers"
    if "!BCH!"=="3" set "EXTRA=!EXTRA! --backend sdwebui"
    if "!BCH!"=="4" set "EXTRA=!EXTRA! --backend comfyui"
    if "!BCH!"=="5" set "EXTRA=!EXTRA! --backend openai"
    if "!BCH!"=="6" set "EXTRA=!EXTRA! --backend placeholder"
)

rem sanitize dangerous chars in free-text inputs
set "TOPIC=%TOPIC:&= - %"
set "TOPIC=%TOPIC:%%= %"
set "TONE=%TONE:&= - %"
set "GENRE=%GENRE:&= - %"
set "TITLE=%TITLE:&= - %"
set "AUTHOR=%AUTHOR:&= - %"

echo.
echo ============================================================
echo    Writing your story... this can take several minutes.
echo ============================================================
echo.
cd /d "%~dp0"

%PY% -m src.pipeline --genre "%GENRE%" --topic "%TOPIC%" --tone "%TONE%" --length "%LEN%" --title "%TITLE%" --author "%AUTHOR%" %EXTRA%

if errorlevel 1 (
    echo.
    echo [Something went wrong - see the messages above.]
    pause
    exit /b 1
)

echo.
echo Done! The PDF has been saved in the "output" folder and should have opened.
pause
