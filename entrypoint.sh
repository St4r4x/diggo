#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-dashboard}"

if [ "$MODE" = "dashboard" ]; then
    cd /app/dashboard
    exec uvicorn app:app --host 0.0.0.0 --port 8000
elif [ "$MODE" = "pipeline" ]; then
    shift
    cd /app
    exec python -m scripts.daily_report "$@"
else
    echo "Unknown mode: $MODE. Use 'dashboard' or 'pipeline'."
    exit 1
fi
