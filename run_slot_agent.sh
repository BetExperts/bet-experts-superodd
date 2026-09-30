#!/bin/bash
# Dagelijkse slot-agent (AboutSlots upcoming p.1 -> nieuwe NL-slots live). LaunchAgent com.betexperts.slotagent.
cd "$(dirname "$0")"
mkdir -p logs
LOCK=/tmp/betexperts-slotagent.lock
if [ -e "$LOCK" ] && kill -0 "$(cat $LOCK)" 2>/dev/null; then exit 0; fi
echo $$ > "$LOCK"; trap 'rm -f "$LOCK"' EXIT
set -a; . ./.env; set +a
echo "=== $(date '+%Y-%m-%d %H:%M') ===" >> logs/slot_agent.log
.venv/bin/python slot_agent.py >> logs/slot_agent.log 2>&1
