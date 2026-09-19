"""GovMind's 24 tools.

Every tool is a Pydantic input model plus an async handler. The model is the
single source of truth: its JSON schema is what Claude sees, and the same model
validates whatever Claude sends back before the handler runs.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .. import events
from ..config import get_settings
from ..schemas import MessageSent, Schema, ToolError
from ..services import blockchain, chart, governance, knowledge, security, treasury
from ..whatsapp.client import get_client


@dataclass
class RunContext:
    """Who the current agent run is talking to."""

    sender_id: str | None = None  # WhatsApp id of the member who triggered the run


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass
class Tool:
    name: str
    description: str
    input_model: type[ToolInput]
    handler: Callable[[Any, RunContext], Awaitable[Any]]
    describe: Callable[[Any], str]

    def to_anthropic(self) -> dict:
        schema = self.input_model.model_json_schema()
        return {"name": self.name, "description": self.description, "input_schema": _strip_titles(schema)}


def _strip_titles(node: Any) -> Any:
    if isinstance(node, dict):
        # Drop pydantic's auto-generated "title" labels, but keep properties that are named "title".
        return {k: _strip_titles(v) for k, v in node.items() if not (k == "title" and isinstance(v, str))}
    if isinstance(node, list):
        return [_strip_titles(v) for v in node]
    return node


TOOLS: dict[str, Tool] = {}


def tool(name: str, description: str, describe: Callable[[Any], str]):
    def register(fn):
        input_model = fn.__annotations__["args"]
        TOOLS[name] = Tool(name, description, input_model, fn, describe)
        return fn

    return register


def _short(addr: str) -> str:
    return addr[:10]


# ─── Governance ──────────────────────────────────────────────────────────


class NoArgs(ToolInput):
    pass


class ProposalRef(ToolInput):
    proposal_number: int = Field(description="The proposal number (e.g., 48)")


class AddressRef(ToolInput):
    address: str = Field(description="The wallet address")


@tool(
    "get_active_proposals",
    'Returns all governance proposals with status "active", including vote tallies and participation rates. '
    "Use this to see what proposals need attention.",
    lambda a: "Fetching active proposals...",
)
async def _active(args: NoArgs, ctx: RunContext):
    return await governance.get_active_proposals()


@tool(
    "get_proposal_detail",
    "Returns the full text, metadata, and vote breakdown for a specific proposal. "
    "Use this when you need to summarise or analyse a specific proposal.",
    lambda a: f"Fetching details for proposal #{a.proposal_number}...",
)
async def _detail(args: ProposalRef, ctx: RunContext):
    return await governance.get_proposal_detail(args.proposal_number)


@tool(
    "get_voting_status",
    "Returns who has voted and who has NOT voted on a given proposal, plus time remaining and participation "
    "rate. Use this for vote mobilisation.",
    lambda a: f"Checking voting status for proposal #{a.proposal_number}...",
)
async def _status(args: ProposalRef, ctx: RunContext):
    return await governance.get_voting_status(args.proposal_number)


@tool(
    "get_member_vote_history",
    "Returns a specific member's past voting record and patterns. Use this to personalise nudge messages "
    "based on how they voted on similar proposals.",
    lambda a: f"Looking up voting history for {_short(a.address)}...",
)
async def _history(args: AddressRef, ctx: RunContext):
    return await governance.get_member_vote_history(args.address)


class CreateProposalArgs(ToolInput):
    title: str = Field(description="Title of the proposal")
    body: str = Field(description="Full text/description of the proposal")
    proposer_address: str = Field(description="Wallet address of the proposer")
    requested_amount: float = Field(description="Amount of EDS requested (0 if no funding needed)")
    recipient_address: str | None = Field(
        None, description="Wallet address to receive funds if proposal passes (defaults to proposer)"
    )
    voting_days: float | None = Field(None, description="Number of days the vote stays open (default: 5)")


@tool(
    "create_proposal",
    "Creates a new governance proposal in the DAO. Records it in the database and on Endless Chain for "
    "immutable proof. Returns the new proposal number.",
    lambda a: f'Creating proposal: "{a.title}" + recording on-chain...',
)
async def _create(args: CreateProposalArgs, ctx: RunContext):
    result = await governance.create_proposal(**args.model_dump())
    return await _with_audit(
        result, "proposal_created", f"Proposal #{result.proposal_number}: {args.title}"
    )


class CastVoteArgs(ToolInput):
    proposal_number: int = Field(description="The proposal number to vote on")
    voter_address: str = Field(description="Wallet address of the voter")
    vote: Literal["for", "against", "abstain"] = Field(description="The vote choice")
    voting_power: float | None = Field(None, description="Voting power (token balance). Default: 1")


@tool(
    "cast_vote",
    "Casts a vote on an active proposal. Records the vote in the database and on Endless Chain. "
    "Each address can only vote once per proposal.",
    lambda a: f'Casting vote "{a.vote}" on Proposal #{a.proposal_number}...',
)
async def _vote(args: CastVoteArgs, ctx: RunContext):
    result = await governance.cast_vote(**args.model_dump())
    if isinstance(result, ToolError):
        return result
    return await _with_audit(
        result,
        "vote_cast",
        f'Vote "{args.vote}" on Proposal #{args.proposal_number} by {args.voter_address}',
    )


async def _with_audit(result: Schema, action_type: str, summary: str) -> Schema:
    try:
        record = await blockchain.record_audit_trail(action_type, summary)
        return result.model_copy(update={"onchain_tx": record.tx_hash, "explorer_url": record.explorer_url})
    except Exception:
        return result.model_copy(update={"onchain_tx": "failed", "explorer_url": None})


@tool(
    "get_group_members",
    "Returns every DAO member who has messaged GovMind on WhatsApp (and so receives DAO broadcasts). "
    "Includes their WhatsApp ID, message count, and last active time. Use this to identify who to nudge.",
    lambda a: "Fetching WhatsApp DAO members...",
)
async def _members(args: NoArgs, ctx: RunContext):
    return await governance.get_group_members()


@tool(
    "get_non_voters",
    "Returns all members who have NOT voted on a specific proposal. Cross-references registered DAO members "
    "and members reachable on WhatsApp. Returns their WhatsApp IDs for sending nudge messages.",
    lambda a: f"Identifying non-voters for Proposal #{a.proposal_number}...",
)
async def _non_voters(args: ProposalRef, ctx: RunContext):
    return await governance.get_non_voters(args.proposal_number)


class LinkWalletArgs(ToolInput):
    whatsapp_id: str = Field(description="The WhatsApp ID (phone number, digits only) to link")
    wallet_address: str = Field(
        description="The Endless Chain wallet address (Base58 like 4T1Jmi...K2qf, or 0x hex)"
    )


class WhatsAppRef(ToolInput):
    whatsapp_id: str = Field(description="The WhatsApp ID (phone number, digits only) to look up")


@tool(
    "link_wallet",
    'Links a WhatsApp user to an Endless Chain wallet address. Use this when a user shares their wallet '
    'address (Base58 format like "4T1Jmi...K2qf" or hex "0x..."). This enables on-chain operations for '
    "that user — checking their EDS balance, sending them EDS, etc.",
    lambda a: f"Linking wallet {_short(a.wallet_address)}... to WhatsApp user {a.whatsapp_id}...",
)
async def _link(args: LinkWalletArgs, ctx: RunContext):
    return await governance.link_wallet(args.whatsapp_id, args.wallet_address)


@tool(
    "get_wallet_for_user",
    "Looks up the linked Endless Chain wallet address for a WhatsApp user. Returns the wallet address if one "
    "has been linked, or null if the user hasn't shared their wallet yet.",
    lambda a: f"Looking up wallet for WhatsApp user {a.whatsapp_id}...",
)
async def _wallet(args: WhatsAppRef, ctx: RunContext):
    return await governance.get_wallet_for_user(args.whatsapp_id)


# ─── Treasury & security ─────────────────────────────────────────────────


class TransactionsArgs(ToolInput):
    direction: Literal["inflow", "outflow"] | None = Field(None, description="Filter by transaction direction")
    category: str | None = Field(
        None, description="Filter by category (e.g., contributor_payment, grant, swap, revenue)"
    )
    days_back: int | None = Field(None, description="Number of days to look back (default: 30)")
    limit: int | None = Field(None, description="Max number of transactions to return (default: 20)")


@tool(
    "get_treasury_summary",
    "Returns current treasury balances, allocation breakdown, monthly burn rate, runway in months, and "
    "concentration risk assessment.",
    lambda a: "Retrieving treasury summary...",
)
async def _treasury(args: NoArgs, ctx: RunContext):
    return await treasury.get_treasury_summary()


@tool(
    "get_treasury_transactions",
    "Returns recent treasury transactions. Can filter by direction (inflow/outflow), category, and time period.",
    lambda a: "Fetching treasury transactions...",
)
async def _txs(args: TransactionsArgs, ctx: RunContext):
    return await treasury.get_transactions(
        direction=args.direction,
        category=args.category,
        days_back=args.days_back if args.days_back is not None else 30,
        limit=args.limit if args.limit is not None else 20,
    )


class TransfersArgs(ToolInput):
    hours_back: int | None = Field(None, description="Number of hours to look back (default: 48)")


@tool(
    "get_token_transfers",
    "Returns recent governance token ($GOV) transfer activity. Use this for attack detection — look for "
    "coordinated accumulation, new wallets, same-source funding.",
    lambda a: "Scanning recent token transfers...",
)
async def _transfers(args: TransfersArgs, ctx: RunContext):
    return await security.get_token_transfers(args.hours_back or 48)


@tool(
    "get_wallet_profile",
    "Returns information about a wallet address including age, transfer history, token balance, and whether "
    "it belongs to a known DAO member. Use for proposer risk assessment and attack investigation.",
    lambda a: f"Profiling wallet {_short(a.address)}...",
)
async def _profile(args: AddressRef, ctx: RunContext):
    return await security.get_wallet_profile(args.address)


class QueryArgs(ToolInput):
    sql: str = Field(description="The SQL SELECT query to execute")


@tool(
    "query_data",
    "Execute a read-only SQL query against the DAO database for ad-hoc data questions. Only SELECT queries "
    "are allowed. Tables: proposals, votes, members, group_members, treasury_transactions, treasury_balances, "
    "token_transfers, knowledge, agent_actions_log, nudge_tracking.",
    lambda a: "Running custom data query...",
)
async def _query(args: QueryArgs, ctx: RunContext):
    return await knowledge.query_data(args.sql)


# ─── WhatsApp messaging ──────────────────────────────────────────────────


class GroupMessageArgs(ToolInput):
    text: str = Field(description="The message text to broadcast to DAO members")
    image_url: str | None = Field(
        None, description="Optional chart_url from generate_chart to attach as an image"
    )


class DirectMessageArgs(ToolInput):
    whatsapp_id: str | None = Field(
        None,
        description="WhatsApp ID (phone number, digits only) of the recipient. "
        "Omit to reply to the member who sent the current message.",
    )
    text: str = Field(description="The message text to send")
    image_url: str | None = Field(None, description="Optional chart_url from generate_chart to attach")


async def _deliver(to: str, text: str, image_url: str | None) -> bool:
    wa = get_client()
    if image_url:
        await wa.send_image(to, image_url)
    return await wa.send_text(to, text)


@tool(
    "send_group_message",
    "Broadcasts a message to the DAO on WhatsApp — every member who has messaged GovMind, plus any configured "
    "broadcast numbers. Use this to post summaries, alerts, answers, and reminders everyone should see.",
    lambda a: "Broadcasting to DAO members on WhatsApp...",
)
async def _broadcast(args: GroupMessageArgs, ctx: RunContext):
    members = await governance.get_group_members()
    recipients = list(dict.fromkeys([m.whatsapp_id for m in members] + get_settings().broadcast_numbers))
    if not recipients:
        return ToolError(error="Nobody has messaged GovMind on WhatsApp yet, so there is no one to broadcast to.")
    results = await asyncio.gather(*(_deliver(r, args.text, args.image_url) for r in recipients))
    await events.whatsapp_sent("group", args.text)
    return MessageSent(
        sent=any(results),
        channel="group",
        text=args.text,
        recipients=[r for r, ok in zip(recipients, results) if ok],
        failed=[r for r, ok in zip(recipients, results) if not ok],
    )


@tool(
    "send_direct_message",
    "Sends a private WhatsApp message to one DAO member. Use this to reply to the member you are talking to, "
    "and for personalised vote nudges (pass their whatsapp_id).",
    lambda a: f"Sending WhatsApp DM to {a.whatsapp_id or 'sender'}...",
)
async def _dm(args: DirectMessageArgs, ctx: RunContext):
    to = args.whatsapp_id or ctx.sender_id
    if not to:
        return ToolError(error="No recipient WhatsApp ID provided and no active sender context.")
    ok = await _deliver(to, args.text, args.image_url)
    await events.whatsapp_sent("dm", args.text, to)
    return MessageSent(sent=ok, channel="dm", text=args.text, recipients=[to] if ok else [], failed=[] if ok else [to])


# ─── Charts & knowledge ──────────────────────────────────────────────────


class Dataset(BaseModel):
    label: str
    data: list[float]


class ChartArgs(ToolInput):
    chart_type: Literal["bar", "line", "pie", "doughnut"] = Field(description="Type of chart to generate")
    title: str = Field(description="Chart title")
    labels: list[str] = Field(description="Labels for the data points")
    datasets: list[Dataset] = Field(description="Datasets to chart")


@tool(
    "generate_chart",
    "Generates a chart image (PNG) from provided data. Returns a chart_url. Pass it as image_url to "
    "send_group_message or send_direct_message so members see the chart inline in WhatsApp.",
    lambda a: f"Generating {a.chart_type} chart: {a.title}...",
)
async def _chart(args: ChartArgs, ctx: RunContext):
    return await chart.generate(args.chart_type, args.title, args.labels, [d.model_dump() for d in args.datasets])


class TermArgs(ToolInput):
    term: str = Field(description='The term or topic to look up (e.g., "runway", "core contributor")')


class StoreKnowledgeArgs(ToolInput):
    term: str = Field(description="The term being defined or corrected")
    definition: str = Field(description="The definition or correction")
    source_user: str = Field(description="Who provided this correction")


@tool(
    "get_knowledge",
    "Retrieves team corrections and definitions from the knowledge base. Always check this before answering "
    "questions to ensure you use team-specific definitions.",
    lambda a: f'Checking knowledge base for "{a.term}"...',
)
async def _get_knowledge(args: TermArgs, ctx: RunContext):
    return await knowledge.get_knowledge(args.term)


@tool(
    "store_knowledge",
    'Stores a new team correction or definition. Use when a team member provides a correction (e.g., "runway '
    'should exclude locked staking").',
    lambda a: f'Storing team correction: "{a.term}"...',
)
async def _store_knowledge(args: StoreKnowledgeArgs, ctx: RunContext):
    return await knowledge.store_knowledge(args.term, args.definition, args.source_user)


class LogActionArgs(ToolInput):
    action_type: Literal[
        "proposal_summary", "vote_nudge", "treasury_alert", "attack_alert", "query_answer", "knowledge_update"
    ] = Field(description="Type of action taken")
    trigger: Literal["scheduled", "new_proposal", "user_question", "anomaly_detected", "manual_trigger"] = Field(
        description="What triggered this action"
    )
    reasoning: str = Field(description="Brief explanation of why you took this action and what you found")
    message_sent: str | None = Field(None, description="The message you sent on WhatsApp (if any)")


@tool(
    "log_action",
    "Records what the agent did and why. Call this as the LAST step of every action for the audit trail.",
    lambda a: "Logging action...",
)
async def _log(args: LogActionArgs, ctx: RunContext):
    return await knowledge.log_action(args.action_type, args.trigger, args.reasoning, args.message_sent)


# ─── Endless Chain ───────────────────────────────────────────────────────


class TransferArgs(ToolInput):
    recipient_address: str = Field(description="The recipient wallet address (Base58 or 0x hex)")
    amount_eds: float = Field(gt=0, description="Amount of EDS tokens to transfer")
    reason: str = Field(description='The reason for this transfer (e.g., "Grant payment for Proposal #48")')


class RecordArgs(ToolInput):
    action_type: str = Field(
        description='Type of action to record (e.g., "proposal_summary", "attack_alert", "treasury_disbursement")'
    )
    summary: str = Field(description="Brief summary of what was decided or detected (hashed and stored on-chain)")


@tool(
    "get_onchain_balance",
    "Reads the real EDS (Endless) token balance for any wallet address on Endless Chain. Use this to verify "
    "actual on-chain balances in real-time, cross-reference treasury holdings, or check a member's funds.",
    lambda a: f"Reading on-chain EDS balance for {_short(a.address)}...",
)
async def _balance(args: AddressRef, ctx: RunContext):
    return await blockchain.get_balance(args.address)


@tool(
    "transfer_eds",
    "Initiates an actual EDS token transfer on Endless Chain. Use this for treasury disbursements, grant "
    "payments, or any authorized on-chain transfer. Returns the transaction hash and explorer URL.",
    lambda a: f"Transferring {a.amount_eds} EDS on Endless Chain...",
)
async def _transfer(args: TransferArgs, ctx: RunContext):
    return await blockchain.transfer_eds(args.recipient_address, args.amount_eds)


@tool(
    "record_action_onchain",
    "Records an agent action as an immutable on-chain audit trail entry on Endless Chain. Creates a "
    "verifiable transaction that proves this action happened. Use after important governance decisions.",
    lambda a: f"Recording {a.action_type} on-chain as immutable audit trail...",
)
async def _record(args: RecordArgs, ctx: RunContext):
    return await blockchain.record_audit_trail(args.action_type, args.summary)


# ─── Dispatch ────────────────────────────────────────────────────────────

ANTHROPIC_TOOLS = [t.to_anthropic() for t in TOOLS.values()]


def to_jsonable(result: Any) -> Any:
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, list):
        return [to_jsonable(r) for r in result]
    return result


async def execute(name: str, raw_input: dict, ctx: RunContext) -> tuple[Any, str, bool]:
    """Validate and run a tool. Returns (json-able result, dashboard description, is_error)."""
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": f"Unknown tool: {name}"}, f"Calling {name}...", True
    try:
        args = spec.input_model.model_validate(raw_input)
    except ValidationError as err:
        return {"error": f"Invalid input for {name}: {err.errors(include_url=False)}"}, f"Calling {name}...", True
    description = spec.describe(args)
    try:
        result = to_jsonable(await spec.handler(args, ctx))
    except Exception as err:
        return {"error": f'Tool "{name}" failed: {err}'}, description, True
    return result, description, isinstance(result, dict) and "error" in result
