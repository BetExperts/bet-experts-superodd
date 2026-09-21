#!/bin/bash
# Wrapper voor de 888Sport 60x-LaunchAgent.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/888.log
.venv/bin/python s888_60x.py >> logs/888.log 2>&1
