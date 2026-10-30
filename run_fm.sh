#!/bin/bash
# Wrapper voor de FootyMetrics value-scanner (LaunchAgent com.betexperts.fmvalue).
cd "$(dirname "$0")" || exit 1
mkdir -p logs
set -a
[ -f .env ] && . ./.env
set +a
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/fm_value.log
.venv/bin/python fm_value.py >> logs/fm_value.log 2>&1
# Team-parels (los script, na de spelers-scan: zelfde Chrome-profiel mag niet tegelijk open)
.venv/bin/python fm_team.py >> logs/fm_team.log 2>&1
# Perfecte picks: aparte melding als er een écht sterke pick bijkomt (aftrap tot morgen 06:00)
.venv/bin/python fm_perfect.py >> logs/fm_perfect.log 2>&1
# VIP-portaal (www.bet-experts.nl/vip/portaal): picks + uitslagen naar Cloudflare KV, alleen bij wijzigingen
.venv/bin/python vip_portaal.py >> logs/vip_portaal.log 2>&1
# VIP-banner in de artikelen bijwerken als ROI/hit rate veranderen (hooguit 1x per 3 uur, Jasper 30-10)
.venv/bin/python vip_cta.py >> logs/vip_cta.log 2>&1
