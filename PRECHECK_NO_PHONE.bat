@echo off
setlocal
cd /d "%~dp0"
echo =============================================
echo LottoLab Mobile v1.1 - NO PHONE PRECHECK
echo =============================================
echo.
where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher not found.
  pause
  exit /b 1
)
echo [1/2] Engine regression and frozen desktop parity...
py -3.13 validate_mobile_v1_1.py
if errorlevel 1 goto :error
echo.
echo [2/2] Android project static audit...
py -3.13 audit_android_project.py
if errorlevel 1 goto :error
echo.
echo PRECHECK PASS. No phone installation was required.
pause
exit /b 0
:error
echo.
echo PRECHECK FAILED. Do not install an APK yet.
pause
exit /b 1
