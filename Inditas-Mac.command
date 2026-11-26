#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Gatekeeper karantén feloldása helyi macOS csomagokon, ha szükséges
for target in "$SCRIPT_DIR/ADO-Agent.app" "$SCRIPT_DIR/ado-agent-cli"; do
  if [ -e "$target" ]; then
    xattr -dr com.apple.quarantine "$target" >/dev/null 2>&1 || true
  fi
done

run_ado() {
  DATA_OPT=()
  if [ -x "$SCRIPT_DIR/ado-agent-cli" ]; then
    chmod +x "$SCRIPT_DIR/ado-agent-cli" >/dev/null 2>&1 || true
    "$SCRIPT_DIR/ado-agent-cli" ${DATA_OPT[@]+"${DATA_OPT[@]}"} "$@"
    return $?
  fi
  if [ -x "$SCRIPT_DIR/ADO-Agent.app/Contents/MacOS/ADO-Agent" ]; then
    "$SCRIPT_DIR/ADO-Agent.app/Contents/MacOS/ADO-Agent" ${DATA_OPT[@]+"${DATA_OPT[@]}"} "$@"
    return $?
  fi
  if [ -x ".venv/bin/python" ]; then
    .venv/bin/python -m ado_agent ${DATA_OPT[@]+"${DATA_OPT[@]}"} "$@"
    return $?
  fi
  PY_BIN="$(command -v python3 || true)"
  if [ -n "$PY_BIN" ]; then
    if [ ! -d ".venv" ]; then
      echo "[ADÓ Agent] Virtuális környezet létrehozása..."
      "$PY_BIN" -m venv .venv
    fi
    if [ -f "requirements.txt" ]; then
      .venv/bin/pip install -q -r requirements.txt
    fi
    .venv/bin/python -m ado_agent ${DATA_OPT[@]+"${DATA_OPT[@]}"} "$@"
    return $?
  fi
  echo "[HIBA] Nem található sem az ADO-Agent app/CLI, sem Python 3 a Mac-en."
  return 1
}
echo "================================================"
echo "  ADÓ Agent indítása macOS Terminalból..."
echo "================================================"
run_ado
RC=$?
if [ $RC -ne 0 ]; then
  echo ""
  read -r -p "Hiba történt ($RC). Nyomj Entert a bezáráshoz..."
fi
