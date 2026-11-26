"""Windows CMD (.bat) és macOS Terminal (.command) 1-kattintásos indítók generálása."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .config import AppConfig


def detect_runtime_target() -> dict[str, str]:
    """Meghatározza az éppen futó bináris vagy forráskód elérési útját."""
    frozen = bool(getattr(sys, "frozen", False))
    exe_path = str(Path(sys.executable).resolve())
    repo_root = str(Path(__file__).resolve().parent.parent)
    return {
        "frozen": "1" if frozen else "0",
        "executable": exe_path,
        "repo_root": repo_root,
        "platform": sys.platform,
    }


def _win_exec_subroutine(exe_hint: str = "", repo_hint: str = "", data_dir: str = "") -> str:
    data_opt = f'--data-dir "{data_dir}" ' if data_dir else ""
    lines = [
        ":exec_ado",
        "setlocal EnableExtensions",
        'cd /d "%~dp0"',
    ]
    if exe_hint and exe_hint.lower().endswith(".exe"):
        lines.extend(
            [
                f'if exist "{exe_hint}" (',
                f'    "{exe_hint}" {data_opt}%*',
                "    exit /b %errorlevel%",
                ")",
            ]
        )
    lines.extend(
        [
            'if exist "%~dp0ADO-Agent-windows-x64.exe" (',
            f'    "%~dp0ADO-Agent-windows-x64.exe" {data_opt}%*',
            "    exit /b %errorlevel%",
            ")",
            'if exist "%~dp0ADO-Agent.exe" (',
            f'    "%~dp0ADO-Agent.exe" {data_opt}%*',
            "    exit /b %errorlevel%",
            ")",
        ]
    )
    if repo_hint:
        lines.extend(
            [
                f'if exist "{repo_hint}\\ado_agent\\app.py" (',
                f'    cd /d "{repo_hint}"',
                ")",
            ]
        )
    lines.extend(
        [
            'if exist ".venv\\Scripts\\python.exe" (',
            f'    ".venv\\Scripts\\python.exe" -m ado_agent {data_opt}%*',
            "    exit /b %errorlevel%",
            ")",
            "where py >nul 2>nul",
            "if %errorlevel%==0 (",
            "    if not exist .venv (",
            "        echo [ADÓ Agent] Virtuális környezet létrehozása...",
            "        py -3 -m venv .venv",
            "    )",
            '    if exist requirements.txt ".venv\\Scripts\\pip.exe" install -q -r requirements.txt',
            f'    ".venv\\Scripts\\python.exe" -m ado_agent {data_opt}%*',
            "    exit /b %errorlevel%",
            ")",
            "where python >nul 2>nul",
            "if %errorlevel%==0 (",
            "    if not exist .venv (",
            "        echo [ADÓ Agent] Virtuális környezet létrehozása...",
            "        python -m venv .venv",
            "    )",
            '    if exist requirements.txt ".venv\\Scripts\\pip.exe" install -q -r requirements.txt',
            f'    ".venv\\Scripts\\python.exe" -m ado_agent {data_opt}%*',
            "    exit /b %errorlevel%",
            ")",
            "echo [HIBA] Nem található sem az ADO-Agent .exe, sem Python 3 a gépen!",
            "exit /b 1",
        ]
    )
    return "\r\n".join(lines)


def generate_windows_web_bat(exe_hint: str = "", repo_hint: str = "", data_dir: str = "") -> bytes:
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "title ADÓ Agent — Webes Irányítópult",
        "call :exec_ado",
        "if errorlevel 1 (",
        "    echo.",
        "    echo Az ADÓ Agent hibával állt le.",
        "    pause",
        ")",
        "exit /b %errorlevel%",
        "",
        _win_exec_subroutine(exe_hint=exe_hint, repo_hint=repo_hint, data_dir=data_dir),
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def generate_windows_cmd_excel_bat(exe_hint: str = "", repo_hint: str = "", data_dir: str = "") -> bytes:
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "title ADÓ Agent — Gyors Ellenőrzés és Excel Export",
        'set "OUT_XLSX=%USERPROFILE%\\Desktop\\ADO-Agent-Jelentes.xlsx"',
        'if exist "%USERPROFILE%\\OneDrive\\Desktop" set "OUT_XLSX=%USERPROFILE%\\OneDrive\\Desktop\\ADO-Agent-Jelentes.xlsx"',
        "echo ========================================================",
        "echo   ADÓ Agent — Ellenőrzés és Excel készítés (CMD)",
        "echo ========================================================",
        'call :exec_ado --scan --export "%OUT_XLSX%"',
        "if errorlevel 1 (",
        "    echo.",
        "    echo Hiba történt az ellenőrzés során.",
        "    pause",
        "    exit /b 1",
        ")",
        "echo.",
        'echo Kész Excel fájl: "%OUT_XLSX%"',
        'if exist "%OUT_XLSX%" start "" "%OUT_XLSX%"',
        "pause",
        "exit /b 0",
        "",
        _win_exec_subroutine(exe_hint=exe_hint, repo_hint=repo_hint, data_dir=data_dir),
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def generate_windows_cmd_menu_bat(exe_hint: str = "", repo_hint: str = "", data_dir: str = "") -> bytes:
    data_target = data_dir or "%LOCALAPPDATA%\\ADO-Agent"
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "title ADÓ Agent — Windows CMD Segítő",
        ":menu",
        "cls",
        "echo =============================================================",
        "echo   ADÓ Agent — Windows CMD Parancssori Segítő",
        "echo =============================================================",
        "echo   [1] Webes irányítópult indítása (1 kattintás + frissítés)",
        "echo   [2] Azonnali ellenőrzés + Excel riport mentése és megnyitása",
        "echo   [3] Csak ellenőrzés futtatása CMD-ben (szöveges összegzés)",
        "echo   [4] Figyelt források listázása",
        "echo   [5] Adatkönyvtár megnyitása Intézőben",
        "echo   [0] Kilépés",
        "echo =============================================================",
        'set "CHOICE="',
        'set /p "CHOICE=Válassz menüpontot (0-5): "',
        'if "%CHOICE%"=="1" ( call :exec_ado & pause & goto :menu )',
        'if "%CHOICE%"=="2" goto :do_excel',
        'if "%CHOICE%"=="3" ( call :exec_ado --scan & pause & goto :menu )',
        'if "%CHOICE%"=="4" ( call :exec_ado --list-sources & pause & goto :menu )',
        f'if "%CHOICE%"=="5" ( if not exist "{data_target}" mkdir "{data_target}" & explorer "{data_target}" & goto :menu )',
        'if "%CHOICE%"=="0" exit /b 0',
        "goto :menu",
        "",
        ":do_excel",
        'set "OUT_XLSX=%USERPROFILE%\\Desktop\\ADO-Agent-Jelentes.xlsx"',
        'if exist "%USERPROFILE%\\OneDrive\\Desktop" set "OUT_XLSX=%USERPROFILE%\\OneDrive\\Desktop\\ADO-Agent-Jelentes.xlsx"',
        'call :exec_ado --scan --export "%OUT_XLSX%"',
        'if not errorlevel 1 if exist "%OUT_XLSX%" start "" "%OUT_XLSX%"',
        "pause",
        "goto :menu",
        "",
        _win_exec_subroutine(exe_hint=exe_hint, repo_hint=repo_hint, data_dir=data_dir),
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _mac_find_runner_block(app_hint: str = "", repo_hint: str = "", data_dir: str = "") -> str:
    # Megjegyzés: macOS gyári /bin/bash 3.2 verzióhoz kompatibilis (nincs set -u üres tömbön)
    data_args_block = (
        f'  DATA_OPT=(--data-dir "{data_dir}")' if data_dir else "  DATA_OPT=()"
    )
    lines = [
        "#!/bin/bash",
        'SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"',
        'cd "$SCRIPT_DIR" || exit 1',
        'export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"',
        "",
        "# Gatekeeper karantén feloldása helyi macOS csomagokon, ha szükséges",
        'for target in "$SCRIPT_DIR/ADO-Agent.app" "$SCRIPT_DIR/ado-agent-cli"; do',
        '  if [ -e "$target" ]; then',
        '    xattr -dr com.apple.quarantine "$target" >/dev/null 2>&1 || true',
        "  fi",
        "done",
        "",
        "run_ado() {",
        data_args_block,
    ]
    if app_hint:
        lines.extend(
            [
                f'  if [ -x "{app_hint}" ]; then',
                f'    "{app_hint}" ${{DATA_OPT[@]+"${{DATA_OPT[@]}}"}} "$@"',
                "    return $?",
                "  fi",
            ]
        )
    lines.extend(
        [
            '  if [ -x "$SCRIPT_DIR/ado-agent-cli" ]; then',
            '    chmod +x "$SCRIPT_DIR/ado-agent-cli" >/dev/null 2>&1 || true',
            '    "$SCRIPT_DIR/ado-agent-cli" ${DATA_OPT[@]+"${DATA_OPT[@]}"} "$@"',
            "    return $?",
            "  fi",
            '  if [ -x "$SCRIPT_DIR/ADO-Agent.app/Contents/MacOS/ADO-Agent" ]; then',
            '    "$SCRIPT_DIR/ADO-Agent.app/Contents/MacOS/ADO-Agent" ${DATA_OPT[@]+"${DATA_OPT[@]}"} "$@"',
            "    return $?",
            "  fi",
        ]
    )
    if repo_hint:
        lines.extend(
            [
                f'  if [ -f "{repo_hint}/ado_agent/app.py" ]; then',
                f'    cd "{repo_hint}" || return 1',
                "  fi",
            ]
        )
    lines.extend(
        [
            '  if [ -x ".venv/bin/python" ]; then',
            '    .venv/bin/python -m ado_agent ${DATA_OPT[@]+"${DATA_OPT[@]}"} "$@"',
            "    return $?",
            "  fi",
            "  PY_BIN=\"$(command -v python3 || true)\"",
            '  if [ -n "$PY_BIN" ]; then',
            '    if [ ! -d ".venv" ]; then',
            '      echo "[ADÓ Agent] Virtuális környezet létrehozása..."',
            '      "$PY_BIN" -m venv .venv',
            "    fi",
            '    if [ -f "requirements.txt" ]; then',
            '      .venv/bin/pip install -q -r requirements.txt',
            "    fi",
            '    .venv/bin/python -m ado_agent ${DATA_OPT[@]+"${DATA_OPT[@]}"} "$@"',
            "    return $?",
            "  fi",
            '  echo "[HIBA] Nem található sem az ADO-Agent app/CLI, sem Python 3 a Mac-en."',
            "  return 1",
            "}",
        ]
    )
    return "\n".join(lines)


def generate_mac_terminal_command(app_hint: str = "", repo_hint: str = "", data_dir: str = "") -> bytes:
    runner = _mac_find_runner_block(app_hint=app_hint, repo_hint=repo_hint, data_dir=data_dir)
    script = "\n".join(
        [
            runner,
            'echo "================================================"',
            'echo "  ADÓ Agent indítása macOS Terminalból..."',
            'echo "================================================"',
            "run_ado",
            "RC=$?",
            "if [ $RC -ne 0 ]; then",
            '  echo ""',
            '  read -r -p "Hiba történt ($RC). Nyomj Entert a bezáráshoz..."',
            "fi",
        ]
    )
    return (script + "\n").encode("utf-8")


def generate_mac_excel_command(app_hint: str = "", repo_hint: str = "", data_dir: str = "") -> bytes:
    runner = _mac_find_runner_block(app_hint=app_hint, repo_hint=repo_hint, data_dir=data_dir)
    script = "\n".join(
        [
            runner,
            'OUT_XLSX="$HOME/Desktop/ADO-Agent-Jelentes.xlsx"',
            'echo "================================================"',
            'echo "  ADÓ Agent — Ellenőrzés és Excel export (Mac)"',
            'echo "================================================"',
            'run_ado --scan --export "$OUT_XLSX"',
            "RC=$?",
            'if [ $RC -eq 0 ] && [ -f "$OUT_XLSX" ]; then',
            '  echo "Kész Excel fájl: $OUT_XLSX"',
            '  open "$OUT_XLSX"',
            "fi",
            'read -r -p "Nyomj Entert a Terminal bezárásához..."',
        ]
    )
    return (script + "\n").encode("utf-8")


def generate_mac_menu_command(app_hint: str = "", repo_hint: str = "", data_dir: str = "") -> bytes:
    runner = _mac_find_runner_block(app_hint=app_hint, repo_hint=repo_hint, data_dir=data_dir)
    data_target = data_dir or "$HOME/Library/Application Support/ADO-Agent"
    script = "\n".join(
        [
            runner,
            "while true; do",
            "  clear",
            '  echo "============================================================="',
            '  echo "  ADÓ Agent — macOS Terminal Segítő"',
            '  echo "============================================================="',
            '  echo "  [1] Webes irányítópult indítása (1 kattintás + frissítés)"',
            '  echo "  [2] Azonnali ellenőrzés + Excel riport az Asztalra"',
            '  echo "  [3] Ellenőrzés futtatása csak Terminálban"',
            '  echo "  [4] Figyelt források listázása"',
            '  echo "  [5] Adatkönyvtár megnyitása Finderben"',
            '  echo "  [0] Kilépés"',
            '  echo "============================================================="',
            '  read -r -p "Válassz menüpontot (0-5): " CHOICE',
            '  case "$CHOICE" in',
            "    1) run_ado ;;",
            '    2) OUT_XLSX="$HOME/Desktop/ADO-Agent-Jelentes.xlsx"',
            '       run_ado --scan --export "$OUT_XLSX" && open "$OUT_XLSX"',
            '       read -r -p "Nyomj Entert a folytatáshoz..." ;;',
            "    3) run_ado --scan",
            '       read -r -p "Nyomj Entert a folytatáshoz..." ;;',
            "    4) run_ado --list-sources",
            '       read -r -p "Nyomj Entert a folytatáshoz..." ;;',
            f'    5) mkdir -p "{data_target}" && open "{data_target}" ;;',
            "    0) exit 0 ;;",
            "  esac",
            "done",
        ]
    )
    return (script + "\n").encode("utf-8")


def resolve_desktop_dir() -> Path:
    if sys.platform == "win32":
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                capture_output=True,
                text=True,
                timeout=4,
            )
            p = proc.stdout.strip()
            if p and Path(p).exists():
                return Path(p)
        except Exception:
            pass
        one_drive = Path.home() / "OneDrive" / "Desktop"
        if one_drive.exists():
            return one_drive
    return Path.home() / "Desktop"


def create_desktop_launchers(config: AppConfig, desktop_dir: Path | None = None) -> list[Path]:
    """Létrehozza az 1-kattintásos Asztali indítókat az aktuális operációs rendszerhez."""
    target_desktop = desktop_dir or resolve_desktop_dir()
    target_desktop.mkdir(parents=True, exist_ok=True)
    runtime = detect_runtime_target()
    frozen = runtime["frozen"] == "1"
    exe_hint = runtime["executable"] if frozen else ""
    repo_hint = "" if frozen else runtime["repo_root"]
    data_dir = str(config.data_dir)

    created: list[Path] = []
    if sys.platform == "win32":
        web_bat = target_desktop / "ADO-Agent Indítás.bat"
        web_bat.write_bytes(generate_windows_web_bat(exe_hint=exe_hint, repo_hint=repo_hint, data_dir=data_dir))
        excel_bat = target_desktop / "ADO-Agent Gyors Excel.bat"
        excel_bat.write_bytes(generate_windows_cmd_excel_bat(exe_hint=exe_hint, repo_hint=repo_hint, data_dir=data_dir))
        cmd_bat = target_desktop / "ADO-Agent CMD Segítő.bat"
        cmd_bat.write_bytes(generate_windows_cmd_menu_bat(exe_hint=exe_hint, repo_hint=repo_hint, data_dir=data_dir))
        created.extend([web_bat, excel_bat, cmd_bat])
    elif sys.platform == "darwin":
        mac_web = target_desktop / "ADO-Agent Terminal.command"
        mac_web.write_bytes(generate_mac_terminal_command(app_hint=exe_hint, repo_hint=repo_hint, data_dir=data_dir))
        mac_web.chmod(0o755)
        mac_excel = target_desktop / "ADO-Agent Gyors Excel.command"
        mac_excel.write_bytes(generate_mac_excel_command(app_hint=exe_hint, repo_hint=repo_hint, data_dir=data_dir))
        mac_excel.chmod(0o755)
        mac_menu = target_desktop / "ADO-Agent Terminal Segítő.command"
        mac_menu.write_bytes(generate_mac_menu_command(app_hint=exe_hint, repo_hint=repo_hint, data_dir=data_dir))
        mac_menu.chmod(0o755)
        created.extend([mac_web, mac_excel, mac_menu])
    else:
        sh_web = target_desktop / "ADO-Agent.sh"
        sh_web.write_bytes(generate_mac_terminal_command(app_hint=exe_hint, repo_hint=repo_hint, data_dir=data_dir))
        sh_web.chmod(0o755)
        created.append(sh_web)
    return created


def open_folder_in_os(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception:
        return False
