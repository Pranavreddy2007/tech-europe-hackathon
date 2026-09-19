"""SQLAlchemy models and async session factory.

Table names match the original schema so `query_data` SQL written by the agent
keeps working: proposals, votes, members, group_members, treasury_transactions,
treasury_balances, token_transfers, knowledge, agent_actions_log, nudge_tracking.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; treat naive datetimes as UTC."""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True)}


class Member(Base):
    __tablename__ = "members"
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    token_balance: Mapped[float] = mapped_column(Numeric(18, 6, asdecimal=False))
    join_date: Mapped[datetime]
    whatsapp_id: Mapped[str | None] = mapped_column(Text)


class GroupMember(Base):
    """A person who has messaged GovMind on WhatsApp (opted in to DAO broadcasts)."""

    __tablename__ = "group_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    whatsapp_id: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    wallet_address: Mapped[str | None] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    proposer_address: Mapped[str] = mapped_column(Text)
    requested_amount: Mapped[float] = mapped_column(Numeric(18, 6, asdecimal=False))
    recipient_address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    vote_start: Mapped[datetime]
    vote_end: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    votes: Mapped[list["Vote"]] = relationship(back_populates="proposal")


class Vote(Base):
    __tablename__ = "votes"
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"))
    voter_address: Mapped[str] = mapped_column(Text)
    vote: Mapped[str] = mapped_column(String(10))
    voting_power: Mapped[float] = mapped_column(Numeric(18, 6, asdecimal=False))
    voted_at: Mapped[datetime]
    proposal: Mapped[Proposal] = relationship(back_populates="votes")


class TreasuryTransaction(Base):
    __tablename__ = "treasury_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    tx_hash: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String(10))
    amount: Mapped[float] = mapped_column(Numeric(18, 6, asdecimal=False))
    token: Mapped[str] = mapped_column(Text)
    counterparty: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    memo: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime]


class TreasuryBalance(Base):
    __tablename__ = "treasury_balances"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(Text)
    balance: Mapped[float] = mapped_column(Numeric(18, 6, asdecimal=False))
    usd_value: Mapped[float] = mapped_column(Numeric(18, 2, asdecimal=False))
    percentage: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


class TokenTransfer(Base):
    __tablename__ = "token_transfers"
    id: Mapped[int] = mapped_column(primary_key=True)
    from_address: Mapped[str] = mapped_column(Text)
    to_address: Mapped[str] = mapped_column(Text)
    amount: Mapped[float] = mapped_column(Numeric(18, 6, asdecimal=False))
    timestamp: Mapped[datetime]


class Knowledge(Base):
    __tablename__ = "knowledge"
    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(Text)
    definition: Mapped[str] = mapped_column(Text)
    source_user: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AgentAction(Base):
    __tablename__ = "agent_actions_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    action_type: Mapped[str] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)
    tools_used: Mapped[list] = mapped_column(JSON, default=list)
    message_sent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class NudgeTracking(Base):
    __tablename__ = "nudge_tracking"
    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(Integer)
    member_address: Mapped[str] = mapped_column(Text)
    nudge_level: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime]


def _engine_args(url: str) -> tuple[str, dict]:
    # asyncpg rejects libpq's ?sslmode=…; translate it to connect_args.
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    connect_args: dict = {}
    if url.startswith("postgresql+asyncpg") and "sslmode" in query:
        if query.pop("sslmode") != "disable":
            connect_args["ssl"] = True
        query.pop("channel_binding", None)
        url = urlunsplit(parts._replace(query=urlencode(query)))
    return url, connect_args


_url, _connect_args = _engine_args(get_settings().database_url)
engine = create_async_engine(_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
