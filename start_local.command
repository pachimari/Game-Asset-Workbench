#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_CMD="cd '$ROOT_DIR' && PYTHONPATH=src python3 -m ai_icon_pipeline.api_launcher --reload"
FRONTEND_CMD="cd '$ROOT_DIR/web' && if [ ! -d node_modules ]; then npm install; fi && npm run dev -- --host 127.0.0.1"

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
