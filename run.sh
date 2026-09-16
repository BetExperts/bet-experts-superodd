#!/bin/bash
# Wrapper voor de LaunchAgent: laadt .env en draait de agent met de venv.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
# Laad secrets uit .env (WEBFLOW_TOKEN, TELEGRAM_BOT_TOKEN, evt. PROXY_*)
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/run.log
.venv/bin/python generate.py >> logs/run.log 2>&1
