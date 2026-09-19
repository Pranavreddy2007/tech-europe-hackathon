"""Pydantic models for everything the services return.

Services hand these back to the agent (serialised with `model_dump(mode="json")`)
and to the REST API, so the shape Gemini sees and the shape the dashboard sees
come from one definition.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

VoteChoice = Literal["for", "against", "abstain"]
Direction = Literal["inflow", "outflow"]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="after")
    @classmethod
    def _utc(cls, v: object) -> object:
        # SQLite returns naive datetimes; everything we store is UTC.
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class ToolError(Schema):
    error: str


# ─── Governance ──────────────────────────────────────────────────────────


class ProposalSummary(Schema):
    proposal_number: int
    title: str
    status: str
    requested_amount: float
    proposer_address: str
    vote_start: datetime
    vote_end: datetime
    total_votes: int
    votes_for: int
    votes_against: int
    votes_abstain: int
    voting_power_for: float
    voting_power_against: float
    participation_rate: str
    total_eligible_voters: int


class ProposalDetail(ProposalSummary):
    body: str
    recipient_address: str | None
    created_at: datetime


class VoterEntry(Schema):
    address: str
    display_name: str
    vote: str
    voting_power: float
    voted_at: datetime


class NonVoterEntry(Schema):
    address: str
    display_name: str | None
    token_balance: float
    whatsapp_id: str | None


class VotingStatus(Schema):
    proposal_number: int
    title: str
    total_eligible: int
    total_voted: int
    participation_rate: str
    time_remaining_hours: int
    time_elapsed_pct: str
    voters: list[VoterEntry]
    non_voters: list[NonVoterEntry]


class VoteHistoryEntry(Schema):
    proposal_number: int | None
    title: str | None
    vote: str
    voting_power: float
    voted_at: datetime
    proposal_status: str | None
    requested_amount: float


class MemberVoteHistory(Schema):
    address: str
    display_name: str | None
    token_balance: float
    join_date: datetime
    whatsapp_id: str | None
    total_proposals_voted: int
    voting_history: list[VoteHistoryEntry]


class GroupMemberOut(Schema):
    whatsapp_id: str
    display_name: str | None
    wallet_address: str | None
    message_count: int
    first_seen: datetime
    last_seen: datetime


class WalletLink(Schema):
    success: bool
    message: str


class WalletLookup(Schema):
    whatsapp_id: str
    wallet_address: str | None
    display_name: str | None


class ProposalCreated(Schema):
    proposal_number: int
    title: str
    proposer_address: str
    requested_amount: float
    vote_start: datetime
    vote_end: datetime
    status: str
    onchain_tx: str | None = None
    explorer_url: str | None = None


class VoteCast(Schema):
    proposal_number: int
    voter: str
    vote: VoteChoice
    voting_power: float
    total_votes_now: int
    participation_rate: str
    onchain_tx: str | None = None
    explorer_url: str | None = None


class RegisteredNonVoter(Schema):
    address: str
    display_name: str | None
    token_balance: float
    whatsapp_id: str | None
    is_on_whatsapp: bool
    last_active: datetime | None


class TrackedNonVoter(Schema):
    whatsapp_id: str
    display_name: str | None
    wallet_address: str | None
    message_count: int
    last_active: datetime


class NonVoters(Schema):
    proposal_number: int
    title: str
    total_votes: int
    registered_non_voters: list[RegisteredNonVoter]
    tracked_whatsapp_non_voters: list[TrackedNonVoter]
    total_whatsapp_members: int


# ─── Treasury ────────────────────────────────────────────────────────────


class Allocation(Schema):
    token: str
    balance: float
    usd_value: float
    percentage: float


class ConcentrationRisk(Schema):
    risk_level: str
    details: str


class TreasurySummary(Schema):
    total_balance_eds: float
    total_balance_usd: float
    allocations: list[Allocation]
    monthly_burn_rate_eds: float
    runway_months: float | None  # None = no burn, infinite runway
    concentration_risk: ConcentrationRisk


class TreasuryTx(Schema):
    tx_hash: str
    direction: str
    amount: float
    token: str
    counterparty: str
    category: str
    memo: str | None
    timestamp: datetime


# ─── Security ────────────────────────────────────────────────────────────


class TransferOut(Schema):
    from_address: str
    to_address: str
    amount: float
    timestamp: datetime


class WalletProfile(Schema):
    address: str
    is_known_member: bool
    display_name: str | None
    token_balance: float
    join_date: datetime | None
    wallet_age_days: int
    first_activity: datetime | None
    total_transfers: int
    sent_count: int
    received_count: int
    total_sent: float
    total_received: float
    recent_transfers: list[TransferOut]


# ─── Knowledge ───────────────────────────────────────────────────────────


class Correction(Schema):
    definition: str
    source_user: str
    created_at: datetime


class KnowledgeResult(Schema):
    found: bool
    term: str
    message: str | None = None
    corrections: list[Correction] = []


class KnowledgeStored(Schema):
    stored: bool
    term: str
    definition: str
    source_user: str


class ActionLogged(Schema):
    logged: bool
    id: int


# ─── Charts / chain / messaging ──────────────────────────────────────────


class ChartResult(Schema):
    chart_url: str
    file_name: str


class Balance(Schema):
    address: str
    balance_eds: float
    balance_raw: str
    network: str


class TransferResult(Schema):
    success: bool
    tx_hash: str
    sender: str
    recipient: str
    amount_eds: float
    network: str
    explorer_url: str


class AuditRecord(Schema):
    success: bool
    tx_hash: str
    action_type: str
    summary_hash: str
    network: str
    explorer_url: str


class MessageSent(Schema):
    sent: bool
    channel: Literal["group", "dm"]
    text: str
    recipients: list[str]
    failed: list[str] = []


class QueryResult(Schema):
    rows: list[dict]
    row_count: int


class HealthResponse(Schema):
    treasury: TreasurySummary
    proposals: list[ProposalSummary]
