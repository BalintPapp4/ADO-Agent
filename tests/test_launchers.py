"""Tesztek a Windows CMD (.bat) és macOS Terminal (.command) 1-kattintásos indítókhoz."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ado_agent.config import AppConfig
from ado_agent.launchers import (
    create_desktop_launchers,
    generate_mac_excel_command,
    generate_mac_menu_command,
    generate_mac_terminal_command,
    generate_windows_cmd_excel_bat,
    generate_windows_cmd_menu_bat,
    generate_windows_web_bat,
)


def test_windows_bat_generators_use_crlf_and_clean_quoting():
    for fn in (generate_windows_web_bat, generate_windows_cmd_excel_bat, generate_windows_cmd_menu_bat):
        raw = fn(exe_hint=r"C:\Tools\ADO-Agent-windows-x64.exe", data_dir=r"C:\Users\Test\ADO-Agent")
        assert b"\r\n" in raw
        text = raw.decode("utf-8")
        assert "chcp 65001" in text
        assert '""%' not in text
        assert 'C:\\Tools\\ADO-Agent-windows-x64.exe' in text


def test_mac_command_generators_pass_bash_syntax(tmp_path: Path):
    for idx, fn in enumerate(
        (generate_mac_terminal_command, generate_mac_excel_command, generate_mac_menu_command)
    ):
        raw = fn(app_hint="/Applications/ADO-Agent.app/Contents/MacOS/ADO-Agent", data_dir="/tmp/ado")
        text = raw.decode("utf-8")
        assert text.startswith("#!/bin/bash\n")
        assert "xattr -dr com.apple.quarantine" in text
        assert "set -u" not in text

        script_path = tmp_path / f"test_{idx}.command"
        script_path.write_bytes(raw)
        subprocess.run(["bash", "-n", str(script_path)], check=True)


def test_create_desktop_launchers(tmp_path: Path):
    cfg = AppConfig(data_dir=tmp_path / "data")
    created = create_desktop_launchers(cfg, desktop_dir=tmp_path / "desktop")
    assert len(created) >= 1
    for p in created:
        assert p.exists()
        assert p.stat().st_size > 100
