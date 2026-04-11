#!/bin/zsh
set -euo pipefail

pkill -f "ai_icon_pipeline.api_launcher" || true
pkill -f "vite --host 127.0.0.1" || true
pkill -f "npm run dev -- --host 127.0.0.1" || true

echo "Stopped local backend and frontend processes."
