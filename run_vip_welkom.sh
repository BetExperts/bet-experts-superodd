#!/bin/bash
# Welkomstbericht naar nieuwe VIP-abonnees (LaunchAgent com.betexperts.vipwelkom, elke 10 min)
cd "$(dirname "$0")" || exit 1
mkdir -p logs
echo "===== $(date '+%Y-%m-%d %H:%M:%S') =====" >> logs/vip_welkom.log
.venv/bin/python vip_welkom.py >> logs/vip_welkom.log 2>&1
