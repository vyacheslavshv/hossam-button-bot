#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Done! Next steps:"
echo "  1. cp .env.example .env  and put your BOT_TOKEN in it"
echo "  2. .venv/bin/python main.py   (tables are created automatically)"
