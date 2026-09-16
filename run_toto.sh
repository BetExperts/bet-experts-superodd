#!/bin/bash
# Wrapper voor de TOTO 50x-LaunchAgent.
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/toto.log
.venv/bin/python toto50x.py >> logs/toto.log 2>&1
