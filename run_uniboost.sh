#!/bin/bash
# Wrapper voor de Unibet Uniboost-LaunchAgent (elk uur op :05).
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/uniboost.log
.venv/bin/python unibet_uniboost.py --publish --post >> logs/uniboost.log 2>&1
