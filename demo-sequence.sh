#!/bin/bash
# GovMind Demo Sequence — 3 Minutes
# Run each command when indicated. Practice timing.
# Usage: bash demo-sequence.sh [backend-url]   (default: http://localhost:8000)

BASE=${1:-https://driftypencil--govmind-web.modal.run}

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║          GovMind — Live Demo Sequence            ║"
echo "║     One Agent. 24 Tools. Four Capabilities.    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# SCENE 1: Proposal Intelligence (0:00 - 0:45)
# Narrative: "A suspicious new proposal just appeared — requesting 80 EDS
# from the treasury for a vague 'strategic partnership'. Watch what GovMind does."
echo "━━━ SCENE 1: Proposal Intelligence (0:00 - 0:45) ━━━"
echo ">> Triggering analysis of Proposal #49 (the suspicious one)..."
echo ""
curl -s -X POST $BASE/trigger/new-proposal \
  -H "Content-Type: application/json" \
  -d '{"proposal_number": 49}' | head -c 200
echo ""
echo ""
echo ">> Watch: Dashboard graph lights up as agent analyses proposal."
echo ">> Watch: WhatsApp broadcast lands with the structured briefing with risk flags."
echo ""
echo "Press ENTER when ready for Scene 2..."
read

# SCENE 2: Vote Mobilisation (0:45 - 1:30)
# Narrative: "Only 17% of members have voted on the Marketing proposal.
# The agent notices and takes action."
echo ""
echo "━━━ SCENE 2: Vote Mobilisation (0:45 - 1:30) ━━━"
echo ">> Triggering voter participation check..."
echo ""
curl -s -X POST $BASE/trigger/vote-check | head -c 200
echo ""
echo ""
echo ">> Watch: Agent identifies non-voters, checks nudge history."
echo ">> Watch: Personalised WhatsApp nudges arrive on team phones."
echo ""
echo "Press ENTER when ready for Scene 3..."
read

# SCENE 3: Treasury Health (1:30 - 2:00)
# Narrative: "A member asks about the treasury on WhatsApp."
echo ""
echo "━━━ SCENE 3: Treasury Health (1:30 - 2:00) ━━━"
echo ">> Asking treasury question..."
echo ""
curl -s -X POST $BASE/trigger/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is our current burn rate and how long will our treasury last? Has spending changed recently?"}' | head -c 200
echo ""
echo ""
echo ">> Watch: Agent queries treasury data, generates chart."
echo ">> Watch: Response with analysis + chart arrives on WhatsApp."
echo ""
echo "Press ENTER when ready for Scene 4..."
read

# SCENE 4: Governance Attack Detection (2:00 - 2:45)
# Narrative: "Meanwhile, the agent has been monitoring token flows.
# It found a coordinated attack pattern."
echo ""
echo "━━━ SCENE 4: Attack Detection (2:00 - 2:45) ━━━"
echo ">> Triggering governance attack scan..."
echo ""
curl -s -X POST $BASE/trigger/attack-check | head -c 200
echo ""
echo ""
echo ">> Watch: Agent scans token transfers, profiles wallets."
echo ">> Watch: GOVERNANCE ALERT posted with evidence + recommendations."
echo ""
echo "Press ENTER for closing..."
read

# CLOSING (2:45 - 3:00)
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║                  DEMO COMPLETE                   ║"
echo "║                                                  ║"
echo "║  One autonomous agent protecting DAO governance  ║"
echo "║  24 tools · 4 capabilities · Real-time dashboard ║"
echo "║                                                  ║"
echo "║     Tech Europe Hackathon · WhatsApp · Modal     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
