#!/bin/bash
# Wrapper voor de LaunchAgent 'Welkomstbonus van de dag' (dagelijks 11:00).
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/welkomstbonus.log
.venv/bin/python welkomstbonus_dag.py --post >> logs/welkomstbonus.log 2>&1
git add state/welkomstbonus_dag.json >/dev/null 2>&1 && git commit -q -m "welkomstbonus-dag: state" >/dev/null 2>&1 && git pull -q --rebase --autostash >/dev/null 2>&1; git push -q >/dev/null 2>&1
exit 0
