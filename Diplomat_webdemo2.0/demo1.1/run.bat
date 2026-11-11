@echo off
chcp 65001 >nul
setlocal
set PYTHONIOENCODING=utf-8

rem ---- 1) explicit override ----
set "PY="
if defined DSH_PYTHON if exist "%DSH_PYTHON%" set "PY=%DSH_PYTHON%"

rem ---- 2) bundled runtime (known good) ----
if not defined PY if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

rem ---- 3) py launcher, but only if it really answers ----
if not defined PY (
    for /f "delims=" %%v in ('py -3 -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PY=py -3"
)

rem ---- 4) python on PATH, but only if it really answers (skips the 0-byte Store stub) ----
if not defined PY (
    for /f "delims=" %%v in ('python -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PY=python"
)

if not defined PY (
    echo.
    echo [error] No working Python found on this machine.
    echo         The "python" in WindowsApps is a 0-byte Store stub, not a real Python.
    echo         Install Python 3 from https://www.python.org/downloads/ and check
    echo         "Add python.exe to PATH" during setup, then run this again.
    echo.
    pause
    exit /b 9009
)

"%PY%" "%~dp0neg_cli.py" %*
set RC=%ERRORLEVEL%
if %RC% NEQ 0 echo.
if %RC% NEQ 0 echo [note] exit code %RC% - see warnings above.
echo.
pause
exit /b %RC%
