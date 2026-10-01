@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo =============================================
echo Lotto Lab Android - Debug APK Builder
echo =============================================
echo.

set "SDK=%LOCALAPPDATA%\Android\Sdk"
if defined ANDROID_HOME set "SDK=%ANDROID_HOME%"

if not exist "%SDK%\platforms\android-36" (
  echo [ERROR] Android SDK 36 was not found.
  echo Install Android Studio, then install Android SDK Platform 36.
  echo Expected SDK: %SDK%
  pause
  exit /b 1
)

> local.properties echo sdk.dir=%SDK:\=\\%

if not defined JAVA_HOME (
  if exist "C:\Program Files\Android\Android Studio\jbr\bin\java.exe" (
    set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
  )
)

if not defined JAVA_HOME (
  echo [ERROR] JAVA_HOME is not set and Android Studio JBR was not found.
  pause
  exit /b 1
)

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher 'py' was not found.
  echo Chaquopy v17 with Python 3.13 requires Python 3.13 on the build PC.
  pause
  exit /b 1
)

py -3.13 -c "import sys; print(sys.version)"
if errorlevel 1 (
  echo [ERROR] Python 3.13 was not found.
  pause
  exit /b 1
)

set "GRADLE_DIR=%~dp0.gradle-bootstrap\gradle-9.4.1"
if not exist "%GRADLE_DIR%\bin\gradle.bat" (
  echo [1/3] Downloading Gradle 9.4.1...
  if not exist "%~dp0.gradle-bootstrap" mkdir "%~dp0.gradle-bootstrap"
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://services.gradle.org/distributions/gradle-9.4.1-bin.zip' -OutFile '%~dp0.gradle-bootstrap\gradle.zip'; Expand-Archive -Force '%~dp0.gradle-bootstrap\gradle.zip' '%~dp0.gradle-bootstrap'"
  if errorlevel 1 (
    echo [ERROR] Gradle download failed.
    pause
    exit /b 1
  )
)

echo [2/3] Building Android project...
call "%GRADLE_DIR%\bin\gradle.bat" --no-daemon :app:assembleDebug
if errorlevel 1 (
  echo.
  echo [ERROR] APK build failed. Open this project in Android Studio and check the Build window.
  pause
  exit /b 1
)

echo.
echo [3/3] BUILD COMPLETE
echo APK:
echo %~dp0app\build\outputs\apk\debug\app-debug.apk
echo.
pause
