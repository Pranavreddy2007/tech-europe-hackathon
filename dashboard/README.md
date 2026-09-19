# GovMind dashboard

Real-time observability for the GovMind agent: a live graph of every tool call, the message feed (Telegram / WhatsApp), DAO health, and demo controls.

## Run locally

Start the backend first (see the [main README](../README.md#quick-start-local-5-minutes)), then:

```bash
npm install
npm run dev        # http://localhost:3000 → talks to the backend at http://localhost:8000
```

Set `NEXT_PUBLIC_BACKEND_URL` to use a different backend, for example the live one:

```bash
NEXT_PUBLIC_BACKEND_URL=https://driftypencil--govmind-web.modal.run npm run dev
```

## Build

```bash
npm run build      # static export to ./out (bundled into the Modal image and served at "/")
```

## Structure

| Path | Purpose |
|---|---|
| `app/page.tsx` | Three-panel layout |
| `app/components/LiveFeed.tsx` | Incoming and outgoing messages, with chart images |
| `app/components/AgentWorkspace.tsx` | The agent neural graph: 24 tool nodes, traversal paths, response panel, run tabs |
| `app/components/DaoHealth.tsx` | Treasury, allocation, proposals, quick actions, **Run Full Demo Sequence**, **Reset Demo** |
| `lib/socket.ts` | Socket.IO client: maps `agent:*` and `whatsapp:*` events into the store |
| `lib/store.ts` | Zustand store: runs, steps, messages |
| `lib/backend.ts` | Backend URL (same origin when served by the backend) |

Event payloads are documented in [docs/API.md](../docs/API.md#4-socketio-events).
