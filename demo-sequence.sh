#!/bin/bash
# GovMind: the 2-minute demo from the terminal (same steps as the dashboard's
# "Run Full Demo Sequence"). Keep the dashboard open to watch the agent graph.
#
# Usage: bash demo-sequence.sh [backend-url]   (default: the live Modal deployment)

set -euo pipefail
BASE=${1:-https://driftypencil--govmind-web.modal.run}

post() {  # post <endpoint> [json-body]; each call returns when the agent run finishes
  if [ $# -ge 2 ]; then
    curl -s -X POST "$BASE/trigger/$1" -H "Content-Type: application/json" -d "$2" | head -c 300
  else
    curl -s -X POST "$BASE/trigger/$1" | head -c 300
  fi
  echo; echo
}

pause() { echo "Press ENTER for the next scene..."; read -r; }

echo "GovMind live demo against $BASE"
echo
echo ">> Resetting demo data (Telegram subscribers are kept)"
post reset-demo
pause

echo "SCENE 1: A member asks whether proposal #49 is safe"
post whatsapp-demo '{"from": "447700900001", "name": "Alice Chen", "text": "Hey GovMind, is proposal 49 safe to vote for?"}'
pause

echo "SCENE 2: An attacker wallet submits proposal #50, and GovMind flags it (Telegram alert)"
post submit-proposal
pause

echo "SCENE 3: Full governance attack scan (second Telegram alert)"
post attack-check
pause

echo "SCENE 4: A member asks for the treasury runway, with a chart"
post whatsapp-demo '{"from": "447700900002", "name": "Bob Martinez", "text": "What'"'"'s our treasury runway? Send me a chart."}'

echo "Demo complete."
