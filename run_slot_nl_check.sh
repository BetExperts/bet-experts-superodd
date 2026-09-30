#!/bin/bash
# Dagelijkse NL-check voor slots (zie slot_nl_check.py). Draait via LaunchAgent com.betexperts.slotnlcheck.
cd "$(dirname "$0")"
mkdir -p logs
echo "=== $(date '+%Y-%m-%d %H:%M') ===" >> logs/slot_nl_check.log
.venv/bin/python slot_nl_check.py --write >> logs/slot_nl_check.log 2>&1
