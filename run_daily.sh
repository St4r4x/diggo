#!/usr/bin/env bash
# Daily job search pipeline: scan portals → generate report → import to dashboard
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATE=$(date +%Y-%m-%d)

# Use .venv if present (local dev), otherwise system python (container)
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python"
fi

echo "=== career-ops-fr daily run — $DATE ==="

echo "[1/2] Generating daily report..."
PYTHONPATH=. $PYTHON scripts/daily_report.py

echo "[2/2] Importing offers into dashboard DB..."
PYTHONPATH=. $PYTHON scripts/import_offers.py

echo "Done — open the dashboard to review new offers."
