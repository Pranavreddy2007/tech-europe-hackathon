# 2-minute demo

**Open:** https://driftypencil--govmind-web.modal.run (dashboard + API on Modal, always warm)

**On your phone:** open [@GovMind_bot](https://t.me/GovMind_bot) and tap **Start** once. For the full Luffa-style experience, add the bot to a Telegram group (your "DAO chat"): alerts post there and members can ask it questions in the group. From then on every alert the agent broadcasts, such as attack scans and flagged proposals, arrives as a push notification. Reset Demo keeps you subscribed.

**Before you start:** click **Reset Demo** (bottom right). The feed and graph clear and the MetaDAO data reloads.

**Go:** click **Run Full Demo Sequence**. It runs four steps back to back, each starting when the previous one finishes (about 100–120s total). The button shows which step is running.

| Time | On screen | What to say |
|---|---|---|
| 0:00 | Dashboard idle | "DAOs hold billions, but under 10% of members vote. Attackers exploit that. GovMind is an AI governance operator that lives in the DAO's Telegram group." |
| ~0:05 | **Alice asks GovMind:** "is proposal 49 safe to vote for?" The graph lights up tool by tool. | "A member just asked GovMind. It's one Pydantic AI agent on Gemini with 24 typed tools. Watch it pull the proposal, profile the proposer's wallet, and check the treasury impact live." |
| ~0:25 | GovMind replies to Alice ("NOT safe"), often with a chart, and broadcasts an ALERT | "It answers Alice directly and warns the whole DAO." |
| ~0:30 | **Attacker submits proposal #50** ("Emergency Liquidity Bridge", 70 EDS). **Your phone buzzes** with 🚨 GOVERNANCE ALERT. | "Now watch: a freshly funded wallet just submitted a proposal to move half the treasury. GovMind flagged it in seconds, and my phone just got the alert." (hold up the phone) |
| ~0:55 | **Attack scan.** Token Transfers and Wallet Profile nodes light up. **Phone buzzes again.** | "It traces the whole attack: one exchange-funded wallet split tokens into fresh wallets that all vote together. Every member gets warned where they already chat." |
| ~1:35 | **Bob asks for a runway chart.** The chart image lands in the feed. | "Ask it anything. It answers with real data and a chart, right in the chat." |
| ~1:50 | COMPLETE, Agent Response panel | "Runs on Modal, typed end to end with Pydantic, and every action can be written to Endless Chain as an audit trail." |

**If something goes wrong:** use the single buttons (*Alice asks: Is #49 safe?*, *🚨 Attacker submits proposal*, *Attack Scan*, *Vote Check*, *Bob asks: Runway chart*). Each takes 15–35s.

**Terminal alternative:** `bash demo-sequence.sh` runs the same four scenes against the live deployment, pausing between them.

**If the page looks frozen or blank:** hard refresh (Cmd+Shift+R). Browsers that cached a page from before the cache-header fix can hold on to an old build.
