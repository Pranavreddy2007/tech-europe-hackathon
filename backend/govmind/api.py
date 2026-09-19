"""HTTP surface: WhatsApp webhook, dashboard API, demo triggers, chart files.

`asgi_app` wraps FastAPI with Socket.IO so one process serves both.
"""

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from typing import Literal

import socketio
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field, ValidationError

from .agent import runner
from .config import get_settings
from .db import init_db
from .events import sio
from .schemas import GroupMemberOut, HealthResponse, WalletLink
from .services import chart, governance, treasury
from .whatsapp.client import verify_signature
from .whatsapp.handler import handle_message
from .whatsapp.models import WebhookPayload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("govmind")

_background: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_finished)


def _finished(task: asyncio.Task) -> None:
    _background.discard(task)
    if not task.cancelled() and task.exception():
        log.error("Background task failed", exc_info=task.exception())


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    s = get_settings()
    log.info("GovMind ready — model=%s whatsapp=%s", s.gemini_model, "on" if s.whatsapp_enabled else "off")
    yield


app = FastAPI(title="GovMind", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def _remember_base_url(request: Request, call_next):
    chart.remember_base_url(str(request.base_url))
    return await call_next(request)


# ─── WhatsApp webhook ────────────────────────────────────────────────────


@app.get("/webhook/whatsapp", response_class=PlainTextResponse)
async def verify_webhook(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
):
    """Meta calls this once when you register the webhook URL."""
    if mode == "subscribe" and token == get_settings().whatsapp_verify_token:
        return challenge
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook/whatsapp")
async def receive_webhook(request: Request):
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=401, detail="Bad signature")
    try:
        payload = WebhookPayload.model_validate_json(raw)
    except ValidationError:
        log.warning("Ignoring unrecognised webhook payload")
        return {"status": "ignored"}
    # Acknowledge immediately — Meta retries anything slower than a few seconds.
    for message, name in payload.iter_messages():
        _spawn(handle_message(message, name))
    return {"status": "ok"}


# ─── Dashboard API ───────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
async def health():
    summary, proposals = await asyncio.gather(treasury.get_treasury_summary(), governance.get_active_proposals())
    return HealthResponse(treasury=summary, proposals=proposals)


@app.get("/api/members", response_model=list[GroupMemberOut])
async def members():
    return await governance.get_group_members()


@app.get("/charts/{name}")
async def chart_file(name: str):
    if not re.fullmatch(r"chart_\d+\.png", name):
        raise HTTPException(status_code=404)
    path = get_settings().chart_dir / name
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/png")


@app.get("/")
async def root():
    return {"name": "GovMind", "status": "ok", "webhook": "/webhook/whatsapp", "health": "/api/health"}


# ─── Demo triggers (used by the dashboard's quick actions) ───────────────


class TriggerResponse(BaseModel):
    trigger: str
    response: str


class NewProposalBody(BaseModel):
    proposal_number: int = 49


class AskBody(BaseModel):
    question: str
    conversation_history: list[str] | None = None


class CreateProposalBody(BaseModel):
    title: str
    body: str
    proposer_address: str = "0xdemo_proposer"
    requested_amount: float = 0
    voting_days: float = 5


class CastVoteBody(BaseModel):
    proposal_number: int
    voter_address: str
    vote: Literal["for", "against", "abstain"]
    voting_power: float = 1


class SimulateMembersBody(BaseModel):
    whatsapp_ids: list[str] | None = None


class TrackMemberBody(BaseModel):
    whatsapp_id: str
    display_name: str | None = None


class LinkWalletBody(BaseModel):
    whatsapp_id: str
    wallet_address: str = Field(min_length=10)


@app.post("/trigger/new-proposal", response_model=TriggerResponse)
async def trigger_new_proposal(body: NewProposalBody | None = None):
    num = (body or NewProposalBody()).proposal_number
    response = await runner.run(
        f"A new governance proposal has been submitted to MetaDAO: Proposal #{num}. "
        "Follow the PROPOSAL INTELLIGENCE process from your instructions. Analyse this proposal thoroughly, "
        "assess the proposer's credibility and wallet history, calculate the exact treasury impact, perform a "
        "risk assessment, and broadcast a comprehensive structured briefing to the DAO on WhatsApp. "
        "Include all sections from the briefing template."
    )
    return TriggerResponse(trigger="new-proposal", response=response)


@app.post("/trigger/vote-check", response_model=TriggerResponse)
async def trigger_vote_check():
    response = await runner.run(
        "Perform a vote mobilisation check on all active MetaDAO proposals. Follow the VOTE MOBILISATION process "
        "from your instructions. Check participation rates, identify non-voters, send personalised WhatsApp "
        "nudges to members who have a whatsapp_id, and broadcast a short summary."
    )
    return TriggerResponse(trigger="vote-check", response=response)


@app.post("/trigger/treasury-check", response_model=TriggerResponse)
async def trigger_treasury_check():
    response = await runner.run(
        "Perform a comprehensive treasury health assessment for MetaDAO. Follow the TREASURY HEALTH process from "
        "your instructions. Check current balances, burn rate, runway, concentration risk, and recent outflows. "
        "Compare the current 30-day burn rate against the 3-month average. Generate a chart showing the treasury "
        "breakdown or burn rate trend. Broadcast your findings and any alerts to the DAO."
    )
    return TriggerResponse(trigger="treasury-check", response=response)


@app.post("/trigger/attack-check", response_model=TriggerResponse)
async def trigger_attack_check():
    response = await runner.run(
        "Perform a governance attack detection scan on MetaDAO. Follow the GOVERNANCE ATTACK DETECTION process "
        "from your instructions. Systematically check all 4 attack patterns: token accumulation before votes, "
        "coordinated wallet funding from the same source, new wallet suspicious activity, and suspicious "
        "proposals. Use get_token_transfers, get_wallet_profile, and query_data to gather evidence. If you find "
        "anything suspicious, broadcast a detailed GOVERNANCE ALERT to the DAO with specific evidence "
        "(addresses, amounts, timestamps) and recommended actions."
    )
    return TriggerResponse(trigger="attack-check", response=response)


@app.post("/trigger/ask", response_model=TriggerResponse)
async def trigger_ask(body: AskBody):
    response = await runner.run(
        f'A DAO member asked the following question: "{body.question}"\n\n'
        "Answer this question using the available tools. Check the knowledge base first for any team-specific "
        "definitions or corrections. Broadcast your answer to the DAO on WhatsApp.",
        history=body.conversation_history,
    )
    return TriggerResponse(trigger="user-question", response=response)


@app.post("/trigger/create-proposal", response_model=TriggerResponse)
async def trigger_create_proposal(body: CreateProposalBody):
    response = await runner.run(
        "A DAO member wants to create a new governance proposal.\n\n"
        f'Title: "{body.title}"\nDescription: "{body.body}"\nProposer address: {body.proposer_address}\n'
        f"Requested amount: {body.requested_amount} EDS\nVoting period: {body.voting_days} days\n\n"
        "Create this proposal using the create_proposal tool, then announce it to the DAO with a structured "
        "briefing. Include the on-chain proof link. Then log the action."
    )
    return TriggerResponse(trigger="create-proposal", response=response)


@app.post("/trigger/cast-vote", response_model=TriggerResponse)
async def trigger_cast_vote(body: CastVoteBody):
    response = await runner.run(
        f"A DAO member wants to vote on Proposal #{body.proposal_number}.\n\n"
        f"Voter address: {body.voter_address}\nVote: {body.vote}\nVoting power: {body.voting_power}\n\n"
        "Cast this vote using the cast_vote tool. Confirm the vote to the DAO with the on-chain proof link. "
        "Then log the action."
    )
    return TriggerResponse(trigger="cast-vote", response=response)


@app.post("/trigger/simulate-members", response_model=list[GroupMemberOut])
async def trigger_simulate_members(body: SimulateMembersBody | None = None):
    """Seed fake WhatsApp members for demos (these numbers won't receive real messages)."""
    defaults = [
        ("447700900001", "Alice"), ("447700900002", "Bob"), ("447700900003", "Carol"),
        ("447700900004", "Dave"), ("447700900005", "Eve"),
    ]
    people = [(i, i) for i in body.whatsapp_ids] if body and body.whatsapp_ids else defaults
    return [await governance.track_group_member(wa_id, name) for wa_id, name in people]


@app.post("/trigger/track-member", response_model=GroupMemberOut)
async def trigger_track_member(body: TrackMemberBody):
    return await governance.track_group_member(body.whatsapp_id, body.display_name)


@app.post("/trigger/link-wallet", response_model=WalletLink)
async def trigger_link_wallet(body: LinkWalletBody):
    return await governance.link_wallet(body.whatsapp_id, body.wallet_address)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return Response(status_code=500, content='{"error":"internal error"}', media_type="application/json")


asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)
