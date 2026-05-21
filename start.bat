@echo off
setlocal

cd /d "%~dp0"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo Starting Audio Conform Syncer local app...
echo.
echo Open the printed local URL in your browser, then press Ctrl+C here to stop.
echo.

python -B -m audio_conform_syncer --app

if errorlevel 1 (
  echo.
  echo Audio Conform Syncer did not start. Confirm Python and FFmpeg are installed, then try:
  echo python -B -m audio_conform_syncer --doctor
  echo.
  pause
)
