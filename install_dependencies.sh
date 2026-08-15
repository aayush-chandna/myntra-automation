#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-time setup: installs Python deps + Playwright browsers.
# Run with:  bash install_dependencies.sh
# ---------------------------------------------------------------------------
set -e

echo "== Checking Python version =="
python3 --version

echo "== Creating virtual environment (./venv) =="
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

echo "== Installing Python packages =="
pip install --upgrade pip
pip install playwright anthropic google-generativeai

echo "== Installing Playwright browser binaries =="
playwright install chromium

echo ""
echo "Setup complete."
echo "Next steps:"
echo "  1. export ANTHROPIC_API_KEY=sk-ant-...   (or GEMINI_API_KEY, and set LLM_BACKEND=gemini)"
echo "  2. python myntra_weekly_order.py --login-setup   # one-time manual Myntra login"
echo "  3. python myntra_weekly_order.py                 # run a weekly order manually / test it"
