#!/bin/bash
# Wrapper voor de Oranje Palace Super Odd-LaunchAgent.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/oranjepalace.log
# Live verversen (--publish). Telegram (--post) staat nog UIT tot het
# partnership rond is en de affiliatelink in het CMS-item staat.
.venv/bin/python op_superodd.py --publish >> logs/oranjepalace.log 2>&1
