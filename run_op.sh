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

# Starcasino Gouden Boost (publiek Altenar-feed, geen browser nodig) — zelfde ritme als de Lucky's Boost.
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/starcasino_goudenboost.log
# 20-10-2026 (gebruiker): Telegram-posts van de Gouden Boost UIT (postte steeds dezelfde boost). Alleen de site bijwerken.
.venv/bin/python sc_goudenboost.py --publish >> logs/starcasino_goudenboost.log 2>&1
