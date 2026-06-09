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
echo "  1. Configure .env (BOT_TOKEN, optionally DATABASE_URL)"
echo "  2. Add models to models.py"
echo "  3. alembic revision --autogenerate -m \"init\""
echo "  4. alembic upgrade head"
echo "  5. python main.py"
