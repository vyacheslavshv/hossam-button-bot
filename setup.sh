#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# aiogram 3.28 needs Python 3.10-3.14. Pick the best interpreter available.
if [ ! -d ".venv" ]; then
    PYTHON=""
    for cand in python3.12 python3.11 python3.13 python3.10 python3.14 python3; do
        if command -v "$cand" >/dev/null 2>&1; then
            ver=$("$cand" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "")
            case "$ver" in
                3.10|3.11|3.12|3.13|3.14) PYTHON="$cand"; break ;;
            esac
        fi
    done
    if [ -z "$PYTHON" ]; then
        echo "Error: need Python 3.10-3.14 (aiogram 3.28 requirement)." >&2
        echo "On Ubuntu:  sudo apt install python3.12-venv" >&2
        exit 1
    fi
    echo "Creating virtual environment with $PYTHON ($($PYTHON --version))..."
    "$PYTHON" -m venv .venv
fi

source .venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Done! Next steps:"
echo "  1. cp .env.example .env   and put your BOT_TOKEN in it"
echo "  2. .venv/bin/python main.py   (tables + data/ created automatically)"
