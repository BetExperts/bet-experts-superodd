#!/bin/bash
# Wrapper voor de JACKS.NL Superboost-LaunchAgent (elk kwartier, 08:00-22:00).
cd "$(dirname "$0")" || exit 1
H=$(date +%H); [ "$H" -lt 8 ] || [ "$H" -gt 22 ] && exit 0
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/jacks_superboost.log
.venv/bin/python jacks_superboost.py --publish --post >> logs/jacks_superboost.log 2>&1
exit 0
