#!/bin/sh
# Fallback for when Ctrl+C doesn't reach run_dev.py (e.g. launched via an IDE's
# debug console instead of a real terminal): force-kills whatever is bound to
# the API and Streamlit ports.
set -e

API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-8501}"

for port in "$API_PORT" "$UI_PORT"; do
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "Killing process(es) on port $port: $pids"
        kill -9 $pids
    fi
done
