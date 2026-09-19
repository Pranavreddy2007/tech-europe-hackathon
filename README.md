<p align="center">
  <img src="https://img.shields.io/badge/Tech_Europe-Hackathon-blueviolet?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Channel-WhatsApp-25D366?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Runs_on-Modal-7FEE64?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Typed_with-Pydantic-E92063?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Chain-Endless-purple?style=for-the-badge" />
</p>

<h1 align="center">GovMind</h1>
<h3 align="center">Autonomous AI Governance Operator for DAOs, on WhatsApp</h3>

<p align="center">
  <em>One Claude agent. Twenty-four tools. Four capabilities. Real on-chain operations on Endless Chain.<br/>
  Lives where your members already are: WhatsApp.</em>
</p>

---

## The problem

DAOs manage billions in assets, but governance runs on apathy:

| Problem | Impact |
|---------|--------|
| **Voter apathy** | < 10% of token holders vote. Proposals moving millions pass with a handful of votes. |
| **Treasury mismanagement** | Nobody watches burn rate or runway until it's too late. |
| **Governance attacks** | Attackers quietly accumulate tokens to drain the treasury. |
| **Information asymmetry** | Only a few insiders actually read the proposals. |

Snapshot and Tally handle voting mechanics, Dune needs SQL, and Discord bots just repost raw proposal text. **GovMind makes every member an informed participant, in the chat app they already open fifty times a day.**

## How it works

GovMind is **one autonomous Claude agent** with **24 tools**. Members message a WhatsApp number; Meta's Cloud API delivers each message to a webhook on **Modal**; the agent investigates with its tools and replies on WhatsApp. It also runs Endless Chain transactions and streams every step to a live dashboard.

```mermaid
flowchart LR
    subgraph WA["WhatsApp"]
        USER[DAO member]
    end

    subgraph MODAL["Modal (serverless)"]
        HOOK["FastAPI webhook<br/>/webhook/whatsapp"]
        AGENT["Claude agent loop<br/>24 Pydantic-typed tools"]
        CRON["modal.Cron<br/>daily attack + vote sweep"]
        VOL[("Modal Volume<br/>charts")]
    end

    DB[(Postgres)]
    CHAIN["Endless Chain"]
    DASH["Next.js dashboard<br/>Socket.IO"]

    USER -- message --> HOOK --> AGENT
    CRON --> AGENT
    AGENT -- reply / broadcast / chart --> USER
    AGENT <--> DB
    AGENT <--> CHAIN
    AGENT --> VOL
    AGENT -- live events --> DASH
```

### WhatsApp as the DAO channel

The WhatsApp Cloud API is one-to-one, so GovMind models the "group" as a **broadcast list**: everyone who has messaged the bot.

| Original group-chat concept | On WhatsApp |
|---|---|
| Reply in the group | `send_direct_message` back to the member who asked |
| Post to the group | `send_group_message` broadcasts to every opted-in member (plus `WHATSAPP_BROADCAST_NUMBERS`) |
| DM nudge | `send_direct_message` to a member's `whatsapp_id` |
| Quick-action buttons | Send **"menu"** to get a WhatsApp list message with one-tap commands |
| Chart links | Charts are attached as real WhatsApp images |
| Member identity | WhatsApp ID (phone number) + profile name, linked to an Endless wallet |

> WhatsApp only allows free-form messages within 24 hours of a member's last message. Sends outside that window come back in the tool result's `failed` list, and the agent reports them instead of retrying. Proactive campaigns outside the window need an approved message template.

## Capabilities

1. **Proposal intelligence.** Summarises proposals, works out treasury impact ("45 EDS, 31% of treasury"), checks the proposer's wallet age and history, rates risk, and broadcasts a structured briefing.
2. **Vote mobilisation.** Finds non-voters and sends each one a personalised WhatsApp nudge. It never tells anyone how to vote.
3. **Treasury health.** Tracks burn rate, runway, concentration risk and new outflow categories. It renders charts and sends them as images.
4. **Attack detection.** Looks for coordinated wallet funding, token accumulation before votes, fresh wallets that are voting, and suspicious proposals. It posts alerts with evidence.

Governance actions such as creating a proposal or casting a vote are also written to **Endless Chain** as an audit trail, and the reply includes an explorer link.

## Where Modal and Pydantic fit

**Modal** ([`backend/modal_app.py`](backend/modal_app.py))
- `web` is an `@modal.asgi_app` serving FastAPI and Socket.IO. It uses `@modal.concurrent` and stays on one container so dashboard sockets and agent runs share state.
- `seed` loads the MetaDAO demo data with `modal run modal_app.py::seed`.
- `daily_sweep` is a `modal.Cron` job that runs an attack scan and a vote check every morning (opt in with `SCHEDULED_CHECKS_ENABLED=true`).
- A `modal.Volume` stores generated charts. All secrets live in one `modal.Secret`.
- The image bundles Node so the Endless TypeScript SDK can sign transactions.

**Pydantic**
- **Tools** ([`agent/tools.py`](backend/govmind/agent/tools.py)): each of the 24 tools is a Pydantic model. Its JSON schema is what Claude sees, and the same model validates Claude's input before the tool runs.
- **Results** ([`schemas.py`](backend/govmind/schemas.py)): every service returns a typed model. Claude and the REST API see the same shape.
- **WhatsApp webhook** ([`whatsapp/models.py`](backend/govmind/whatsapp/models.py)): Meta's payloads are parsed into typed models, with HMAC signature checks.
- **Config** ([`config.py`](backend/govmind/config.py)): `pydantic-settings` reads env vars or the Modal secret.

## Agent tools (24)

| Group | Tools |
|---|---|
| Governance | `get_active_proposals` · `get_proposal_detail` · `get_voting_status` · `get_member_vote_history` · `create_proposal` · `cast_vote` · `get_group_members` · `get_non_voters` |
| Wallets & chain | `link_wallet` · `get_wallet_for_user` · `get_onchain_balance` · `transfer_eds` · `record_action_onchain` |
| Treasury | `get_treasury_summary` · `get_treasury_transactions` |
| Security | `get_token_transfers` · `get_wallet_profile` |
| WhatsApp | `send_group_message` (broadcast) · `send_direct_message` |
| Utility | `query_data` (read-only SQL) · `generate_chart` · `get_knowledge` · `store_knowledge` · `log_action` |

## Repository layout

```
backend/
  modal_app.py            Modal app: web endpoint, seed job, daily cron
  govmind/
    api.py                FastAPI routes: WhatsApp webhook, /api, /trigger, /charts
    agent/                Claude tool loop, system prompt, Pydantic tools
    whatsapp/             Cloud API client, webhook models, message handler
    services/             governance, treasury, security, knowledge, charts, chain
    db.py  schemas.py     SQLAlchemy tables + Pydantic result models
    seed.py               MetaDAO demo data (47 members, proposals #40–#49, attack pattern)
  chain/endless.mjs       Endless Chain signer (TypeScript SDK, called from Python)
  tests/                  pytest suite
dashboard/                Next.js live dashboard (agent graph, WhatsApp feed, DAO health)
demo-sequence.sh          Scripted 3-minute demo
```

## Setup

### 1. WhatsApp Cloud API

1. Create an app at [developers.facebook.com](https://developers.facebook.com) and add the **WhatsApp** product.
2. Note the **Phone number ID** and create a **permanent access token** (System User with `whatsapp_business_messaging`).
3. Note the **App secret** (App settings → Basic), which is used to verify webhook signatures.
4. Add your team's phones as test recipients (or use a production number).

### 2. Deploy to Modal

```bash
cd backend
pip install modal && modal setup
modal secret create govmind-secrets \
  ANTHROPIC_API_KEY=sk-ant-... \
  WHATSAPP_ACCESS_TOKEN=... WHATSAPP_PHONE_NUMBER_ID=... \
  WHATSAPP_VERIFY_TOKEN=pick-any-string WHATSAPP_APP_SECRET=... \
  DATABASE_URL=postgresql://user:pass@host/db \
  ENDLESS_PRIVATE_KEY=0x...
modal run modal_app.py::seed
modal deploy modal_app.py
```

`modal deploy` prints a URL like `https://<you>--govmind-web.modal.run`. In the Meta dashboard, go to **WhatsApp → Configuration → Webhook**, set the callback URL to `<url>/webhook/whatsapp` with your verify token, and subscribe to the **messages** field.

Leave out `DATABASE_URL` and the app falls back to SQLite on the Modal Volume. After seeding, restart the `web` app so it picks up the data. Any hosted Postgres (Neon, Supabase, …) works; the URL is converted to `asyncpg` automatically.

### 3. Dashboard

```bash
cd dashboard
npm install
NEXT_PUBLIC_BACKEND_URL=https://<you>--govmind-web.modal.run npm run dev
```

### Local development

```bash
cd backend
uv venv && uv pip install -e ".[dev]"
cp .env.example .env               # fill in keys; SQLite is the default DB
python -m govmind.seed
uvicorn govmind.api:asgi_app --reload --port 8000
pytest
```

Expose `:8000` with a tunnel (e.g. `ngrok http 8000`) to receive WhatsApp webhooks locally, or run `modal serve modal_app.py` for a live-reloading Modal URL.

## Try it

Message the bot on WhatsApp:

- `menu` → one-tap command list
- `Is proposal 49 safe?`
- `What's our runway? Show me a chart`
- `my wallet is 4T1JmiB34KERKGVxUMNXXZJSRngzwWS5KTP4AcgtK2qf` → links your wallet, shows your EDS balance
- `Runway should exclude locked staking` → stored as a team correction

Or drive the demo from the dashboard's Quick Actions, or with `bash demo-sequence.sh <backend-url>`.

## Tech stack

| Layer | Tech |
|---|---|
| Agent | Claude (`claude-opus-5` by default, set via `ANTHROPIC_MODEL`), Anthropic Python SDK, manual tool loop with parallel tool calls |
| Runtime | Modal (ASGI web endpoint, Cron, Volume, Secrets) |
| API | FastAPI, python-socketio |
| Typing | Pydantic v2, pydantic-settings |
| Messaging | WhatsApp Cloud API (Meta Graph API) |
| Data | SQLAlchemy 2 (async), Postgres / SQLite |
| Charts | matplotlib |
| Chain | Endless Chain via `@endlesslab/endless-ts-sdk` |
| Dashboard | Next.js, React, Zustand, Socket.IO client, Tailwind |
