@echo off
chcp 65001 >nul
title ADO Agent
cd /d "%~dp0"

echo ==========================================
echo   ADO Agent inditasa (Windows)
echo ==========================================
echo.

if not exist "requirements.txt" (
    echo [HIBA] Nem talalhato a requirements.txt ebben a mappaban!
    echo Tedd ezt a fajlt kozvetlenul az ADO-Agent fo mappajaba ^(a README.md melle^).
    echo.
    pause
    exit /b 1
)

if exist ".venv\Scripts\python.exe" goto check_deps

echo [1/2] Virtualis kornyezet letrehozasa...
set "PY_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if defined PY_CMD goto make_venv

python --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=python"
if defined PY_CMD goto make_venv

echo [HIBA] Nem talalhato Python ezen a gepen!
echo Toltsd le innen: https://www.python.org/downloads/
echo Telepiteskor pipald be az "Add python.exe to PATH" opciot!
echo.
pause
exit /b 1

:make_venv
%PY_CMD% -m venv .venv
if errorlevel 1 (
    echo [HIBA] Nem sikerult letrehozni a .venv kornyezetet.
    echo.
    pause
    exit /b 1
)

:check_deps
if exist ".venv\.deps_installed" goto run_app

echo [2/2] Fuggosegek telepitese / ellenorzese...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [HIBA] A fuggosegek telepitese sikertelen volt.
    echo.
    pause
    exit /b 1
)
echo ok > ".venv\.deps_installed"

:run_app
echo.
echo ADO Agent elinditva. A bongeszo hamarosan megnyilik...
echo ^(Hasznalat kozben hagyd nyitva ezt az ablakot. Leallitas: Ctrl+C vagy ablak bezarasa.^)
echo.

".venv\Scripts\python.exe" -m ado_agent
if errorlevel 1 (
    echo.
    echo [HIBA] A program hibaval allt le.
    pause
)
