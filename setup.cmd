@echo off
rem Double-click to set up everything for testing (Windows).
rem Finds or installs Python 3.11+, then runs scripts\onboard.py. Extra arguments are passed on,
rem e.g.  setup.cmd --yes --offline
setlocal
cd /d "%~dp0"
title KM Assistant setup

call :find_python
if not defined PY (
    echo Python 3.11 or newer was not found.
    where winget >nul 2>nul
    if errorlevel 1 goto :no_python
    choice /c YN /m "Install Python 3.11 now with winget"
    if errorlevel 2 goto :no_python
    winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    call :find_python
    if not defined PY (
        echo Python was installed. Close this window and double-click setup.cmd again.
        goto :end
    )
)

%PY% scripts\onboard.py %*
goto :end

:find_python
set "PY="
for %%V in (3.13 3.12 3.11) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul && set "PY=python"
)
exit /b 0

:no_python
echo Install Python 3.11+ from https://www.python.org/downloads/ (tick "Add python.exe to PATH"),
echo then double-click setup.cmd again.

:end
echo.
pause
