#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_DIR="$ROOT_DIR/.local/run"
mkdir -p "$RUN_DIR"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"
BACKEND_CMD="cd '$ROOT_DIR' && mkdir -p .local/run && export PYTHONPATH=src && python3 -m ai_icon_pipeline.api_launcher --reload & echo \$! > '$BACKEND_PID_FILE' && wait \$!"
FRONTEND_CMD="cd '$ROOT_DIR/web' && mkdir -p '$RUN_DIR' && if [ ! -d node_modules ]; then npm install; fi && npm run dev -- --host 127.0.0.1 & echo \$! > '$FRONTEND_PID_FILE' && wait \$!"

osascript <<EOF
tell application "Terminal"
    activate
    do script "$BACKEND_CMD"
    do script "$FRONTEND_CMD"
end tell
EOF

echo ""
echo "Started backend on http://127.0.0.1:8000 and frontend on http://127.0.0.1:5173"
echo "You can now open http://127.0.0.1:5173/"
