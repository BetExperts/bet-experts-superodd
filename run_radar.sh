#!/bin/bash
# Wrapper voor de promo-radar-LaunchAgent (08:40 en 14:40).
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/promo_radar.log
.venv/bin/python promo_radar.py >> logs/promo_radar.log 2>&1
# state terugzetten in de repo (afbeeldingen pusht de radar zelf)
git add state/promo_radar.json state/rubrieken.json >/dev/null 2>&1 && git commit -q -m "promo-radar: state" >/dev/null 2>&1 && git pull -q --rebase --autostash >/dev/null 2>&1; git push -q >/dev/null 2>&1
exit 0
