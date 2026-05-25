#!/usr/bin/env bash
# Daily job search pipeline: scan portals → generate report → import to dashboard
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATE=$(date +%Y-%m-%d)

echo "=== career-ops-fr daily run — $DATE ==="

echo "[1/2] Generating daily report..."
.venv/bin/python scripts/daily_report.py

echo "[2/2] Importing offers into dashboard DB..."
.venv/bin/python scripts/import_offers.py

echo "Done — open the dashboard to review new offers."
