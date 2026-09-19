# 2-minute demo

**Open:** https://driftypencil--govmind-web.modal.run (dashboard + API on Modal, always warm)

**Before you start:** click **Reset Demo** (bottom right). The feed and graph clear and the MetaDAO data reloads.

**Go:** click **Run Full Demo Sequence**. It runs four steps back to back, each starting when the previous one finishes (about 100–120s total). The button shows which step is running.

| Time | On screen | What to say |
|---|---|---|
| 0:00 | Dashboard idle | "DAOs hold billions, but under 10% of members vote. Attackers exploit that. GovMind is an AI governance operator that lives in WhatsApp." |
| ~0:05 | **Alice asks on WhatsApp:** "is proposal 49 safe to vote for?" The graph lights up tool by tool. | "A member just asked on WhatsApp. It's one Pydantic AI agent on Gemini with 24 typed tools. Watch it pull the proposal, profile the proposer's wallet, and check the treasury impact live." |
| ~0:25 | GovMind replies to Alice ("NOT safe"), often with a chart, and broadcasts an ALERT | "It answers Alice directly and warns the whole DAO." |
| ~0:30 | **Attack scan.** Token Transfers and Wallet Profile nodes light up. | "Now it scans for governance attacks: one exchange-funded wallet split tokens into three fresh wallets, all voting *for* #49. That's a Sybil attack, caught with evidence." |
| ~1:00 | **Vote mobilisation.** DM nudges and a broadcast appear in the feed. | "It fights apathy too: it finds who hasn't voted and sends each one a personal WhatsApp nudge. It never tells anyone how to vote." |
| ~1:35 | **Bob asks for a runway chart.** The chart image lands in the feed. | "Ask it anything. It answers with real data and a chart, right in WhatsApp." |
| ~1:50 | COMPLETE, Agent Response panel | "Runs on Modal, typed end to end with Pydantic, and every action can be written to Endless Chain as an audit trail." |

**If something goes wrong:** use the single buttons (*WhatsApp: Is #49 safe?*, *Attack Scan*, *Vote Check*, *WhatsApp: Runway chart*). Each takes 15–35s.
