#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-dashboard}"

if [ "$MODE" = "dashboard" ]; then
    cd /app
    export PYTHONPATH=/app:/app/dashboard
    exec uvicorn dashboard.app:app --host 0.0.0.0 --port 8000
elif [ "$MODE" = "pipeline" ]; then
    shift
    cd /app
    python -m scripts.daily_report "$@"
    exec python -m scripts.import_offers "$@"
else
    echo "Unknown mode: $MODE. Use 'dashboard' or 'pipeline'."
    exit 1
fi
