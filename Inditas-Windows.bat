@echo off
chcp 65001 >nul
title ADÓ Agent — Webes Irányítópult
call :exec_ado
if errorlevel 1 (
    echo.
    echo Az ADÓ Agent hibával állt le.
    pause
)
exit /b %errorlevel%

:exec_ado
setlocal EnableExtensions
cd /d "%~dp0"
if exist "%~dp0ADO-Agent-windows-x64.exe" (
    "%~dp0ADO-Agent-windows-x64.exe" %*
    exit /b %errorlevel%
)
if exist "%~dp0ADO-Agent.exe" (
    "%~dp0ADO-Agent.exe" %*
    exit /b %errorlevel%
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m ado_agent %*
    exit /b %errorlevel%
)
where py >nul 2>nul
if %errorlevel%==0 (
    if not exist .venv (
        echo [ADÓ Agent] Virtuális környezet létrehozása...
        py -3 -m venv .venv
    )
    if exist requirements.txt ".venv\Scripts\pip.exe" install -q -r requirements.txt
    ".venv\Scripts\python.exe" -m ado_agent %*
    exit /b %errorlevel%
)
where python >nul 2>nul
if %errorlevel%==0 (
    if not exist .venv (
        echo [ADÓ Agent] Virtuális környezet létrehozása...
        python -m venv .venv
    )
    if exist requirements.txt ".venv\Scripts\pip.exe" install -q -r requirements.txt
    ".venv\Scripts\python.exe" -m ado_agent %*
    exit /b %errorlevel%
)
echo [HIBA] Nem található sem az ADO-Agent .exe, sem Python 3 a gépen!
exit /b 1
