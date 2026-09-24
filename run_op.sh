#!/bin/bash
# Wrapper voor de Oranje Palace Super Odd-LaunchAgent.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/oranjepalace.log
# Live verversen (--publish) + Telegram-teaser bij een nieuwe boost (--post).
# Partnership + affiliatelink live sinds 24-09-2026.
.venv/bin/python op_superodd.py --publish --post >> logs/oranjepalace.log 2>&1
