#!/bin/bash
# Wrapper voor de TOTO Lekker Man-LaunchAgent (elk uur op :50).
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/lekkerman.log
.venv/bin/python toto_lekkerman.py --publish --post >> logs/lekkerman.log 2>&1
