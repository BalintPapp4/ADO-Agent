"""Platformfüggetlen PyInstaller build szkript (Windows .exe, macOS .app + CLI, Linux)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_pyinstaller(args: list[str]) -> None:
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", *args]
    print("Futtatás:", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def common_data_args() -> list[str]:
    sep = os.pathsep
    return [
        "--add-data",
        f"ado_agent/web/templates{sep}ado_agent/web/templates",
        "--add-data",
        f"ado_agent/web/static{sep}ado_agent/web/static",
        "--collect-submodules",
        "ado_agent",
        "--hidden-import",
        "lxml.etree",
        "--hidden-import",
        "lxml._elementpath",
        "--hidden-import",
        "feedparser",
        "--hidden-import",
        "waitress",
        "--hidden-import",
        "openpyxl",
    ]


def main() -> int:
    dist_dir = ROOT / "dist"
    build_dir = ROOT / "build"
    release_dir = ROOT / "release_artifacts"
    shutil.rmtree(release_dir, ignore_errors=True)
    release_dir.mkdir(parents=True, exist_ok=True)

    entry = str(ROOT / "scripts" / "pyinstaller_entry.py")

    if sys.platform == "win32":
        run_pyinstaller(
            [
                "--onefile",
                "--name",
                "ADO-Agent",
                *common_data_args(),
                entry,
            ]
        )
        exe_path = dist_dir / "ADO-Agent.exe"
        target = release_dir / "ADO-Agent-windows-x64.exe"
        shutil.copy2(exe_path, target)
        for bat_name in ("Inditas-Windows.bat", "ADO-Agent-CMD-Segito.bat"):
            bat_src = ROOT / bat_name
            if bat_src.exists():
                shutil.copy2(bat_src, release_dir / bat_name)
        print(f"Kész Windows futtatható fájl és CMD indítók: {release_dir}")

    elif sys.platform == "darwin":
        # 1. Duplakattintásos macOS .app csomag
        run_pyinstaller(
            [
                "--windowed",
                "--onedir",
                "--name",
                "ADO-Agent",
                "--osx-bundle-identifier",
                "hu.adoagent.app",
                *common_data_args(),
                entry,
            ]
        )
        # 2. Terminálból is hívható CLI bináris
        run_pyinstaller(
            [
                "--onefile",
                "--name",
                "ado-agent-cli",
                *common_data_args(),
                entry,
            ]
        )
        stage_dir = release_dir / "_macos_stage"
        stage_dir.mkdir(parents=True, exist_ok=True)
        app_bundle = dist_dir / "ADO-Agent.app"
        cli_bin = dist_dir / "ado-agent-cli"
        subprocess.run(["cp", "-a", str(app_bundle), str(stage_dir / "ADO-Agent.app")], check=True)
        subprocess.run(["cp", "-a", str(cli_bin), str(stage_dir / "ado-agent-cli")], check=True)
        for cmd_name in ("Inditas-Mac.command", "ADO-Agent-Mac-Terminal-Segito.command"):
            cmd_src = ROOT / cmd_name
            if cmd_src.exists():
                dst = stage_dir / cmd_name
                shutil.copy2(cmd_src, dst)
                dst.chmod(0o755)
        zip_path = release_dir / "ADO-Agent-macos.zip"
        subprocess.run(["zip", "-ry", str(zip_path), "."], cwd=stage_dir, check=True)
        shutil.rmtree(stage_dir, ignore_errors=True)
        print(f"Kész macOS csomag (.app + CLI + Terminal indítók): {zip_path}")

    else:
        run_pyinstaller(
            [
                "--onefile",
                "--name",
                "ADO-Agent",
                *common_data_args(),
                entry,
            ]
        )
        bin_path = dist_dir / "ADO-Agent"
        target = release_dir / "ADO-Agent-linux-x64"
        shutil.copy2(bin_path, target)
        print(f"Kész Linux bináris: {target}")

    # Tisztítás csak ha kérték
    if os.environ.get("ADO_CLEAN_BUILD") == "1":
        shutil.rmtree(build_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
