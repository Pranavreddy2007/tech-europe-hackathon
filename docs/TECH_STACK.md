# Tech stack

Every framework, API, service and tool GovMind uses: what it is, why it was chosen, and where it lives in the code. Versions are those the project was built and tested with. Python minimums are pinned in [`backend/pyproject.toml`](../backend/pyproject.toml), JavaScript versions in [`dashboard/package.json`](../dashboard/package.json).

## AI and agent

| Tool | Version | Role | Where |
|---|---|---|---|
| [Pydantic AI](https://ai.pydantic.dev) (`pydantic-ai-slim[google]`) | 2.46 | Agent framework. Runs the tool-calling loop against Gemini (function calling, Gemini thought signatures, retries, usage limits). GovMind steps it with `agent.iter()` to stream every tool call to the dashboard | `agent/runner.py` |
| [Google Gemini API](https://ai.google.dev) (`google-genai`) | model `gemini-3.5-flash`, SDK 2.24 | The model behind the agent. Thinking level `low` keeps full runs within 13–37 s | `agent/runner.py` via `GoogleModel` |
| [Pydantic AI Gateway](https://ai.pydantic.dev/gateway/) | optional | Alternative way to reach Gemini with one key (`PYDANTIC_AI_GATEWAY_API_KEY`) | `agent/runner.py` |

## Typing and validation

| Tool | Version | Role | Where |
|---|---|---|---|
| [Pydantic](https://docs.pydantic.dev) | 2.13 | Tool input models (their JSON schema is sent to Gemini, and the same model validates Gemini's arguments), typed service results, webhook payload models, request and response bodies | `agent/tools.py`, `schemas.py`, `telegram/models.py`, `whatsapp/models.py`, `api.py` |
| [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | 2.15 | Typed configuration from env vars / `.env` / Modal secret | `config.py` |

## Runtime and deployment

| Tool | Version | Role | Where |
|---|---|---|---|
| [Modal](https://modal.com) | 1.5 | Serverless runtime. `modal.Image` (Python 3.12 + Node 20 + deps + dashboard), `@modal.asgi_app` web endpoint, `@modal.concurrent`, one warm container (`min/max_containers=1`), `modal.Volume` (SQLite, charts, chain key), `modal.Secret`, `modal.Cron` daily sweep, seed function | `backend/modal_app.py`, `backend/deploy.sh` |
| [uv](https://docs.astral.sh/uv/) | latest | Fast Python dependency installs, locally and in the Modal image | `modal_app.py` (`uv_pip_install`) |

## Backend

| Tool | Version | Role | Where |
|---|---|---|---|
| [Python](https://www.python.org) | 3.11+ (3.12 on Modal) | Backend language | `backend/` |
| [FastAPI](https://fastapi.tiangolo.com) | 0.141 | HTTP API: webhooks, dashboard API, triggers, charts, static dashboard, OpenAPI docs | `api.py` |
| [python-socketio](https://python-socketio.readthedocs.io) | 5.17 | Real-time agent events to the dashboard (ASGI app wrapping FastAPI) | `events.py`, `api.py` |
| [SQLAlchemy](https://www.sqlalchemy.org) (async) | 2.0 | ORM and query layer for proposals, votes, members, treasury, transfers, knowledge, logs | `db.py`, `services/` |
| [asyncpg](https://github.com/MagicStack/asyncpg) | 0.31 | Postgres driver (production DB option) | `db.py` |
| [aiosqlite](https://github.com/omnilib/aiosqlite) | 0.22 | SQLite driver (default, local and on the Modal volume) | `db.py` |
| [httpx](https://www.python-httpx.org) | 0.28 | Async HTTP client for the Telegram and WhatsApp APIs and the Endless reachability check | `telegram/client.py`, `whatsapp/client.py`, `services/blockchain.py` |
| [matplotlib](https://matplotlib.org) | 3.11 | Renders bar, line, pie and doughnut charts to PNG for chat messages | `services/chart.py` |
| [Uvicorn](https://www.uvicorn.org) | 0.53 | ASGI server for local development | README quick start |

## Messaging

| Service | Role | Where |
|---|---|---|
| [Telegram Bot API](https://core.telegram.org/bots/api) | Primary channel. Webhook with secret token, DAO group chat, private chats, reply keyboard, chart photos, typing indicator, alerts to the group and to every private subscriber | `telegram/` |
| [WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api) (Meta Graph API v21.0) | Secondary channel. Signed webhook, text/image/interactive list messages, read receipts; demo mode without credentials | `whatsapp/` |

## Blockchain

| Tool | Version | Role | Where |
|---|---|---|---|
| Endless Chain | testnet (`rpc-test.endless.link`) | On-chain balances, EDS transfers, immutable audit records, faucet-funded agent account | `services/blockchain.py` |
| [`@endlesslab/endless-ts-sdk`](https://www.npmjs.com/package/@endlesslab/endless-ts-sdk) | 1.0.7+ | Official SDK for signing and submitting transactions (Endless has no Python SDK), called from Python as a small Node CLI | `backend/chain/endless.mjs` |
| [Node.js](https://nodejs.org) | 20 | Runs the Endless signer (installed in the Modal image) | `modal_app.py` |

## Dashboard

| Tool | Version | Role | Where |
|---|---|---|---|
| [Next.js](https://nextjs.org) | 16.2 | Dashboard app, built as a static export and served by the backend at `/` | `dashboard/` |
| [React](https://react.dev) | 19.2 (with React Compiler) | UI | `dashboard/app/` |
| [TypeScript](https://www.typescriptlang.org) | 5 | Dashboard language | `dashboard/` |
| [Zustand](https://zustand.docs.pmnd.rs) | 5 | Client state: runs, steps, messages | `dashboard/lib/store.ts` |
| [socket.io-client](https://socket.io/docs/v4/client-api/) | 4.8 | Receives live agent events | `dashboard/lib/socket.ts` |
| [Tailwind CSS](https://tailwindcss.com) | 4 | Styling | `dashboard/app/globals.css` |
| SVG + CSS animations | none | The live agent graph: nodes, traversal paths and moving particles | `dashboard/app/components/AgentWorkspace.tsx`, `globals.css` |

## Testing and quality

| Tool | Version | Role |
|---|---|---|
| [pytest](https://pytest.org) + pytest-asyncio | 9.1 | 16 backend tests (services, SQL guard, tool schemas, webhooks, Telegram groups, cache headers, agent loop) |
| Pydantic AI `FunctionModel` | built in | Scripted model for testing the agent loop without API calls |
| FastAPI `TestClient` | built in | Webhook and endpoint tests |
| TypeScript compiler / ESLint | 5 / 9 | Dashboard type-check and lint |

## Why these choices

- **Pydantic AI + Pydantic.** One Pydantic model per tool gives Gemini a precise schema and validates its output with the same definition: invalid arguments become a message to the model, not a crash. Typed results mean the model and the dashboard see the same shapes.
- **Gemini 3.5 Flash with low thinking.** Fast enough for a live demo (each run 13–37 s over up to about 15 tool calls) while still following multi-step procedures.
- **Modal.** One Python file defines the image, web endpoint, storage, secrets and cron. No servers, Dockerfiles or tunnels, and a stable HTTPS URL for Telegram and Meta webhooks.
- **Telegram first.** Instant bot setup, real groups, no 24-hour messaging window, and reliable push notifications, which makes it the closest match to the group-chat experience the original GovMind had on Luffa.
- **Node signer for Endless.** Endless only ships a TypeScript SDK; calling it as a tiny CLI keeps transaction signing on the official code path.
