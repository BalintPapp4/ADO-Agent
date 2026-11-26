@echo off
chcp 65001 >nul
title ADÓ Agent — Windows CMD Segítő
:menu
cls
echo =============================================================
echo   ADÓ Agent — Windows CMD Parancssori Segítő
echo =============================================================
echo   [1] Webes irányítópult indítása (1 kattintás + frissítés)
echo   [2] Azonnali ellenőrzés + Excel riport mentése és megnyitása
echo   [3] Csak ellenőrzés futtatása CMD-ben (szöveges összegzés)
echo   [4] Figyelt források listázása
echo   [5] Adatkönyvtár megnyitása Intézőben
echo   [0] Kilépés
echo =============================================================
set "CHOICE="
set /p "CHOICE=Válassz menüpontot (0-5): "
if "%CHOICE%"=="1" ( call :exec_ado & pause & goto :menu )
if "%CHOICE%"=="2" goto :do_excel
if "%CHOICE%"=="3" ( call :exec_ado --scan & pause & goto :menu )
if "%CHOICE%"=="4" ( call :exec_ado --list-sources & pause & goto :menu )
if "%CHOICE%"=="5" ( if not exist "%LOCALAPPDATA%\ADO-Agent" mkdir "%LOCALAPPDATA%\ADO-Agent" & explorer "%LOCALAPPDATA%\ADO-Agent" & goto :menu )
if "%CHOICE%"=="0" exit /b 0
goto :menu

:do_excel
set "OUT_XLSX=%USERPROFILE%\Desktop\ADO-Agent-Jelentes.xlsx"
if exist "%USERPROFILE%\OneDrive\Desktop" set "OUT_XLSX=%USERPROFILE%\OneDrive\Desktop\ADO-Agent-Jelentes.xlsx"
call :exec_ado --scan --export "%OUT_XLSX%"
if not errorlevel 1 if exist "%OUT_XLSX%" start "" "%OUT_XLSX%"
pause
goto :menu

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
