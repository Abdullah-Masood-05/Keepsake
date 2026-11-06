@echo off
REM ============================================================
REM  build.bat - Master build: Nuitka compile + Inno Setup
REM  Produces: installer_output\Fetchly-Setup-2.0.4.exe
REM ============================================================

setlocal enabledelayedexpansion

REM Always run from the folder containing this script.
cd /d "%~dp0"

echo ============================================
echo  Fetchly - Build Pipeline
echo  Version 2.0.4
echo ============================================
echo.

REM --- Configuration ---
set PYTHON=.venv\Scripts\python.exe
set SCRIPT=main.py
set EXE_NAME=Fetchly
set APP_VERSION=2.0.4.0
set JOBS=%NUMBER_OF_PROCESSORS%
set FFMPEG_DIR=ffmpeg

REM --- Verify Python ---
if not exist "%PYTHON%" (
    echo ERROR: Python not found at %PYTHON%
    echo Run: uv sync
    pause
    exit /b 1
)

REM --- Verify icon ---
if not exist "resources\icons\app.ico" (
    echo ERROR: resources\icons\app.ico not found.
    pause
    exit /b 1
)

REM --- Check ffmpeg (optional) ---
set HAVE_FFMPEG=0
if exist "%FFMPEG_DIR%\ffmpeg.exe" (
    set HAVE_FFMPEG=1
) else (
    echo WARNING: %FFMPEG_DIR%\ffmpeg.exe not found.
    echo The app will build, but merging video+audio and audio
    echo conversion will not work until ffmpeg.exe is placed next to
    echo the installed exe or on PATH.
    echo   - Build it from the ffmpeg-ytdl-minimal-build repo, or
    echo   - Download from https://github.com/yt-dlp/FFmpeg-Builds/releases
    echo     and put ffmpeg.exe ^(and ffprobe.exe^) in the %FFMPEG_DIR%\ folder.
    echo.
)

REM --- Step 1: Clean ---
echo [1/4] Cleaning previous builds...
if exist build_dist rmdir /s /q build_dist
if exist installer_output rmdir /s /q installer_output
mkdir installer_output
echo       Done.
echo.

REM --- Step 2: Nuitka compile ---
echo [2/4] Compiling with Nuitka (single .exe)...
echo       This may take 5-10 minutes on first run...
echo.

REM Notes:
REM  --lto=no : MSVC whole-program link (LTO) over the huge object set
REM             appeared to hang forever at "Backend C linking".
REM  --noinclude-custom-mode=yt_dlp.extractor:bytecode : ship yt-dlp's
REM             ~970 extractor modules as bytecode instead of C. This cuts
REM             the C files from ~1100 to ~150 and the build dir from
REM             1.8 GB to ~170 MB. Extractors are not performance critical.
REM  --include-package(-data)=yt_dlp_ejs : the extractors are bytecode, so Nuitka
REM             does not see their lazy "import yt_dlp_ejs.yt.solver"; ship the
REM             YouTube JS challenge solver and its .js files explicitly.
REM  Data files are found at runtime relative to the main module's __file__.
"%PYTHON%" -m nuitka ^
    --onefile ^
    --windows-console-mode=disable ^
    --lto=no ^
    --jobs=%JOBS% ^
    --enable-plugin=pyqt6 ^
    --noinclude-custom-mode=yt_dlp.extractor:bytecode ^
    --include-package=yt_dlp_ejs ^
    --include-package-data=yt_dlp_ejs ^
    --nofollow-import-to=unittest,test,pytest,_pytest,doctest,pdb ^
    --nofollow-import-to=setuptools,pip,distutils,pkg_resources ^
    --noinclude-setuptools-mode=nofollow ^
    --python-flag=no_docstrings ^
    --include-qt-plugins=sensible,styles,platforms ^
    --include-data-files=resources\icons\app.ico=resources\icons\app.ico ^
    --include-data-files=resources\icons\app.png=resources\icons\app.png ^
    --windows-icon-from-ico=resources\icons\app.ico ^
    --company-name="Abdullah Masood" ^
    --product-name="Fetchly" ^
    --file-description="Fetchly" ^
    --file-version=%APP_VERSION% ^
    --product-version=%APP_VERSION% ^
    --copyright="Copyright (c) 2026 Abdullah Masood" ^
    --assume-yes-for-downloads ^
    --output-filename=%EXE_NAME%.exe ^
    --output-dir=build_dist ^
    --remove-output ^
    %SCRIPT%

if errorlevel 1 (
    echo.
    echo BUILD FAILED!
    echo Check the output above for errors.
    pause
    exit /b 1
)

echo.
echo       Nuitka compile complete.
echo.

REM --- Verify output ---
if not exist "build_dist\%EXE_NAME%.exe" (
    echo ERROR: %EXE_NAME%.exe not found after build!
    pause
    exit /b 1
)

REM --- Step 3: Copy FFmpeg next to the exe (for the standalone build) ---
echo [3/4] Copying FFmpeg...
if "%HAVE_FFMPEG%"=="1" (
    copy /y "%FFMPEG_DIR%\ffmpeg.exe" "build_dist\ffmpeg.exe" >nul
    echo       ffmpeg.exe copied to build_dist.
    if exist "%FFMPEG_DIR%\ffprobe.exe" (
        copy /y "%FFMPEG_DIR%\ffprobe.exe" "build_dist\ffprobe.exe" >nul
        echo       ffprobe.exe copied to build_dist.
    )
) else (
    echo       Skipping ffmpeg ^(not found in %FFMPEG_DIR%\^).
)
echo.

REM --- Step 4: Inno Setup ---
echo [4/4] Building installer with Inno Setup...

REM Find ISCC.exe
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
) else (
    where ISCC.exe >nul 2>&1 && set ISCC=ISCC.exe
)

if not defined ISCC (
    echo WARNING: Inno Setup not found!
    echo Install from: https://jrsoftware.org/isinfo.php
    echo.
    echo Build complete without installer:
    echo   build_dist\%EXE_NAME%.exe
    pause
    exit /b 0
)

%ISCC% installer.iss
if errorlevel 1 (
    echo.
    echo Inno Setup failed, but the exe was built successfully.
    echo   build_dist\%EXE_NAME%.exe
    pause
    exit /b 1
)

echo.
echo ============================================
echo  BUILD COMPLETE!
echo.
echo  Installer: installer_output\Fetchly-Setup-2.0.4.exe
echo  Standalone: build_dist\%EXE_NAME%.exe
if "%HAVE_FFMPEG%"=="0" echo  NOTE: built WITHOUT ffmpeg.
echo ============================================
echo.
pause
