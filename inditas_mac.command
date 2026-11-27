#!/bin/bash

cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "=========================================="
echo "  ADÓ Agent indítása (macOS)"
echo "=========================================="
echo ""

if [ ! -f "requirements.txt" ]; then
    echo "[HIBA] Nem található a requirements.txt ebben a mappában!"
    echo "Tedd ezt a fájlt közvetlenül az ADO-Agent fő mappájába (a README.md mellé)."
    echo ""
    read -r -p "Nyomj Entert a bezáráshoz..."
    exit 1
fi

VENV_DIR=".venv_mac"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[1/2] Virtuális környezet létrehozása..."
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    else
        echo "[HIBA] Nem található Python 3 ezen a Macen!"
        echo "Telepítsd innen: https://www.python.org/downloads/ vagy Homebrew-val: brew install python"
        echo ""
        read -r -p "Nyomj Entert a bezáráshoz..."
        exit 1
    fi

    "$PYTHON_BIN" -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "[HIBA] Nem sikerült létrehozni a virtuális környezetet."
        echo ""
        read -r -p "Nyomj Entert a bezáráshoz..."
        exit 1
    fi
fi

if [ ! -f "$VENV_DIR/.deps_installed" ]; then
    echo "[2/2] Függőségek telepítése / ellenőrzése..."
    "$VENV_DIR/bin/python" -m pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[HIBA] A függőségek telepítése sikertelen volt."
        echo ""
        read -r -p "Nyomj Entert a bezáráshoz..."
        exit 1
    fi
    touch "$VENV_DIR/.deps_installed"
fi

echo ""
echo "ADÓ Agent elindítva. A böngésző hamarosan megnyílik..."
echo "(Használat közben hagyd nyitva ezt az ablakot. Leállítás: Ctrl+C)"
echo ""

"$VENV_DIR/bin/python" -m ado_agent
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[HIBA] A program hibával állt le (kód: $EXIT_CODE)."
    read -r -p "Nyomj Entert a bezáráshoz..."
fi
