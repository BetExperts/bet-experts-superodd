#!/bin/bash
# Wrapper voor de LaunchAgent storingsmelder-check (elke 5 minuten).
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
{ echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="; .venv/bin/python storing_check.py; } >> logs/storing_check.log 2>&1
# log klein houden
tail -n 3000 logs/storing_check.log > logs/storing_check.tmp && mv logs/storing_check.tmp logs/storing_check.log
exit 0
