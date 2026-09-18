#!/bin/bash
# Wrapper voor de Oranje Palace Super Odd-LaunchAgent.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/oranjepalace.log
# PRE-PARTNERSHIP: gestaged, geen Telegram. Zodra de deal rond is en de
# affiliatelink in het CMS-item staat: voeg '--publish --post' toe.
.venv/bin/python op_superodd.py >> logs/oranjepalace.log 2>&1
