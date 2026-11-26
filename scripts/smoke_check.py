"""Cross-platform smoke test a lefordított ADÓ Agent binárisokhoz (Windows, macOS, Linux)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


def main() -> int:
    if len(sys.argv) < 2:
        print("Használat: python scripts/smoke_check.py <futtathato_fajl>")
        return 2

    binary = Path(sys.argv[1]).resolve()
    if not binary.exists():
        print(f"Hiányzó bináris: {binary}")
        return 1

    # 1. CLI --version & --list-sources
    subprocess.run([str(binary), "--version"], check=True)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([str(binary), "--data-dir", tmp, "--list-sources"], check=True)

        # 2. Webes felület és beágyazott sablonok / statikus fájlok ellenőrzése
        port = 18765
        proc = subprocess.Popen(
            [
                str(binary),
                "--data-dir",
                tmp,
                "--port",
                str(port),
                "--no-browser",
                "--no-auto-scan",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            base_url = f"http://127.0.0.1:{port}"
            ready = False
            for _ in range(40):
                if proc.poll() is not None:
                    out, err = proc.communicate(timeout=2)
                    raise RuntimeError(f"A szerver idő előtt leállt: {out!r} {err!r}")
                try:
                    r = httpx.get(f"{base_url}/api/health", timeout=1.0)
                    if r.status_code == 200:
                        ready = True
                        break
                except Exception:
                    time.sleep(0.25)

            if not ready:
                raise RuntimeError("A webes szerver nem indult el időben.")

            r_home = httpx.get(f"{base_url}/", timeout=2.0)
            assert r_home.status_code == 200 and "ADÓ Agent" in r_home.text

            r_css = httpx.get(f"{base_url}/static/style.css", timeout=2.0)
            assert r_css.status_code == 200

            r_js = httpx.get(f"{base_url}/static/app.js", timeout=2.0)
            assert r_js.status_code == 200

            r_state = httpx.get(f"{base_url}/api/state", timeout=2.0)
            assert r_state.status_code == 200 and len(r_state.json()["sources"]) >= 7

            r_shut = httpx.post(f"{base_url}/api/shutdown", timeout=2.0)
            assert r_shut.status_code == 200

            proc.wait(timeout=5)
            print(f"Smoke teszt SIKERES: {binary}")
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
