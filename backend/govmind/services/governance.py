import logging
from datetime import timedelta

from sqlalchemy import func, select

from ..db import GroupMember, Member, Proposal, Vote, aware, session_scope, utcnow
from ..schemas import (
    GroupMemberOut,
    MemberVoteHistory,
    NonVoterEntry,
    NonVoters,
    ProposalCreated,
    ProposalDetail,
    ProposalSummary,
    RegisteredNonVoter,
    ToolError,
    TrackedNonVoter,
    VoteCast,
    VoteChoice,
    VoteHistoryEntry,
    VoterEntry,
    VotingStatus,
    WalletLink,
    WalletLookup,
)

log = logging.getLogger(__name__)


def _pct(part: int, whole: int) -> str:
    return f"{part / max(whole, 1) * 100:.1f}%"


def _tally(p: Proposal, votes: list[Vote], total_members: int) -> dict:
    by = {c: [v for v in votes if v.vote == c] for c in ("for", "against", "abstain")}
    return dict(
        proposal_number=p.proposal_number,
        title=p.title,
        status=p.status,
        requested_amount=p.requested_amount,
        proposer_address=p.proposer_address,
        vote_start=aware(p.vote_start),
        vote_end=aware(p.vote_end),
        total_votes=len(votes),
        votes_for=len(by["for"]),
        votes_against=len(by["against"]),
        votes_abstain=len(by["abstain"]),
        voting_power_for=sum(v.voting_power for v in by["for"]),
        voting_power_against=sum(v.voting_power for v in by["against"]),
        participation_rate=_pct(len(votes), total_members),
        total_eligible_voters=total_members,
    )


async def _votes_for(session, proposal_id: int) -> list[Vote]:
    return list((await session.scalars(select(Vote).where(Vote.proposal_id == proposal_id))).all())


async def _proposal(session, number: int) -> Proposal | None:
    return await session.scalar(select(Proposal).where(Proposal.proposal_number == number))


async def get_active_proposals() -> list[ProposalSummary]:
    async with session_scope() as s:
        proposals = (
            await s.scalars(select(Proposal).where(Proposal.status == "active").order_by(Proposal.vote_end))
        ).all()
        total = await s.scalar(select(func.count(Member.id))) or 0
        return [ProposalSummary(**_tally(p, await _votes_for(s, p.id), total)) for p in proposals]


async def get_proposal_detail(proposal_number: int) -> ProposalDetail | ToolError:
    async with session_scope() as s:
        p = await _proposal(s, proposal_number)
        if not p:
            return ToolError(error=f"Proposal #{proposal_number} not found")
        total = await s.scalar(select(func.count(Member.id))) or 0
        return ProposalDetail(
            **_tally(p, await _votes_for(s, p.id), total),
            body=p.body,
            recipient_address=p.recipient_address,
            created_at=aware(p.created_at),
        )


async def get_voting_status(proposal_number: int) -> VotingStatus | ToolError:
    async with session_scope() as s:
        p = await _proposal(s, proposal_number)
        if not p:
            return ToolError(error=f"Proposal #{proposal_number} not found")
        votes = await _votes_for(s, p.id)
        members = list((await s.scalars(select(Member))).all())

    by_address = {m.address: m for m in members}
    voted = {v.voter_address for v in votes}
    start, end, now = aware(p.vote_start), aware(p.vote_end), utcnow()
    remaining = (end - now).total_seconds()
    duration = max((end - start).total_seconds(), 1)

    return VotingStatus(
        proposal_number=p.proposal_number,
        title=p.title,
        total_eligible=len(members),
        total_voted=len(votes),
        participation_rate=_pct(len(votes), len(members)),
        time_remaining_hours=max(0, round(remaining / 3600)),
        time_elapsed_pct=f"{min(100.0, (duration - remaining) / duration * 100):.0f}%",
        voters=[
            VoterEntry(
                address=v.voter_address,
                display_name=(by_address[v.voter_address].display_name if v.voter_address in by_address else None)
                or "Unknown",
                vote=v.vote,
                voting_power=v.voting_power,
                voted_at=aware(v.voted_at),
            )
            for v in votes
        ],
        non_voters=[NonVoterEntry.model_validate(m) for m in members if m.address not in voted],
    )


async def get_member_vote_history(address: str) -> MemberVoteHistory | ToolError:
    async with session_scope() as s:
        member = await s.scalar(select(Member).where(Member.address == address))
        if not member:
            return ToolError(error=f"Member {address} not found")
        rows = (
            await s.execute(
                select(Vote, Proposal)
                .join(Proposal, Proposal.id == Vote.proposal_id)
                .where(Vote.voter_address == address)
                .order_by(Vote.voted_at.desc())
            )
        ).all()

    return MemberVoteHistory(
        address=member.address,
        display_name=member.display_name,
        token_balance=member.token_balance,
        join_date=aware(member.join_date),
        whatsapp_id=member.whatsapp_id,
        total_proposals_voted=len(rows),
        voting_history=[
            VoteHistoryEntry(
                proposal_number=p.proposal_number,
                title=p.title,
                vote=v.vote,
                voting_power=v.voting_power,
                voted_at=aware(v.voted_at),
                proposal_status=p.status,
                requested_amount=p.requested_amount,
            )
            for v, p in rows
        ],
    )


# ─── WhatsApp member tracking ────────────────────────────────────────────


async def track_group_member(whatsapp_id: str, display_name: str | None = None) -> GroupMemberOut:
    async with session_scope() as s:
        gm = await s.scalar(select(GroupMember).where(GroupMember.whatsapp_id == whatsapp_id))
        if gm:
            gm.message_count += 1
            gm.last_seen = utcnow()
            if display_name:
                gm.display_name = display_name
        else:
            gm = GroupMember(whatsapp_id=whatsapp_id, display_name=display_name, message_count=1)
            s.add(gm)
            log.info("New WhatsApp member tracked: %s", whatsapp_id)
        await s.flush()
        return GroupMemberOut.model_validate(gm)


async def get_group_members() -> list[GroupMemberOut]:
    async with session_scope() as s:
        rows = (await s.scalars(select(GroupMember).order_by(GroupMember.last_seen.desc()))).all()
        return [GroupMemberOut.model_validate(r) for r in rows]


async def get_broadcast_list() -> list[str]:
    """Everyone reachable on WhatsApp: people who messaged GovMind plus registered members with a number."""
    async with session_scope() as s:
        tracked = (await s.scalars(select(GroupMember.whatsapp_id))).all()
        registered = (await s.scalars(select(Member.whatsapp_id).where(Member.whatsapp_id.is_not(None)))).all()
    return list(dict.fromkeys([*tracked, *registered]))


async def get_group_member(whatsapp_id: str) -> GroupMemberOut | None:
    async with session_scope() as s:
        gm = await s.scalar(select(GroupMember).where(GroupMember.whatsapp_id == whatsapp_id))
        return GroupMemberOut.model_validate(gm) if gm else None


async def link_wallet(whatsapp_id: str, wallet_address: str) -> WalletLink:
    async with session_scope() as s:
        gm = await s.scalar(select(GroupMember).where(GroupMember.whatsapp_id == whatsapp_id))
        if gm:
            gm.wallet_address = wallet_address
        else:
            s.add(GroupMember(whatsapp_id=whatsapp_id, wallet_address=wallet_address, message_count=0))
    log.info("Wallet linked: %s -> %s", whatsapp_id, wallet_address)
    return WalletLink(success=True, message=f"Wallet {wallet_address} linked to WhatsApp user {whatsapp_id}")


async def get_wallet_for_user(whatsapp_id: str) -> WalletLookup:
    gm = await get_group_member(whatsapp_id)
    return WalletLookup(
        whatsapp_id=whatsapp_id,
        wallet_address=gm.wallet_address if gm else None,
        display_name=gm.display_name if gm else None,
    )


# ─── Proposals & votes ───────────────────────────────────────────────────


async def create_proposal(
    title: str,
    body: str,
    proposer_address: str,
    requested_amount: float,
    recipient_address: str | None = None,
    voting_days: float | None = None,
) -> ProposalCreated:
    now = utcnow()
    vote_end = now + timedelta(days=voting_days or 5)
    async with session_scope() as s:
        next_num = (await s.scalar(select(func.max(Proposal.proposal_number))) or 0) + 1
        s.add(
            Proposal(
                proposal_number=next_num,
                title=title,
                body=body,
                proposer_address=proposer_address,
                requested_amount=requested_amount,
                recipient_address=recipient_address or proposer_address,
                status="active",
                vote_start=now,
                vote_end=vote_end,
            )
        )
    log.info("Proposal #%s created: %s", next_num, title)
    return ProposalCreated(
        proposal_number=next_num,
        title=title,
        proposer_address=proposer_address,
        requested_amount=requested_amount,
        vote_start=now,
        vote_end=vote_end,
        status="active",
    )


async def cast_vote(
    proposal_number: int, voter_address: str, vote: VoteChoice, voting_power: float | None = None
) -> VoteCast | ToolError:
    power = voting_power if voting_power is not None else 1
    async with session_scope() as s:
        p = await _proposal(s, proposal_number)
        if not p:
            return ToolError(error=f"Proposal #{proposal_number} not found")
        if p.status != "active":
            return ToolError(error=f"Proposal #{proposal_number} is not active (status: {p.status})")
        existing = await s.scalar(
            select(Vote).where(Vote.proposal_id == p.id, Vote.voter_address == voter_address)
        )
        if existing:
            return ToolError(error=f"{voter_address} has already voted on Proposal #{proposal_number}")
        s.add(Vote(proposal_id=p.id, voter_address=voter_address, vote=vote, voting_power=power, voted_at=utcnow()))
        await s.flush()
        total_votes = await s.scalar(select(func.count(Vote.id)).where(Vote.proposal_id == p.id)) or 0
        total_members = await s.scalar(select(func.count(Member.id))) or 0

    log.info('Vote cast: %s voted "%s" on Proposal #%s', voter_address, vote, proposal_number)
    return VoteCast(
        proposal_number=proposal_number,
        voter=voter_address,
        vote=vote,
        voting_power=power,
        total_votes_now=total_votes,
        participation_rate=_pct(total_votes, total_members),
    )


async def get_non_voters(proposal_number: int) -> NonVoters | ToolError:
    async with session_scope() as s:
        p = await _proposal(s, proposal_number)
        if not p:
            return ToolError(error=f"Proposal #{proposal_number} not found")
        votes = await _votes_for(s, p.id)
        members = list((await s.scalars(select(Member))).all())
        group = list((await s.scalars(select(GroupMember))).all())

    voted = {v.voter_address for v in votes}
    registered_ids = {m.whatsapp_id for m in members if m.whatsapp_id}

    def group_entry(m: Member) -> GroupMember | None:
        return next((g for g in group if g.whatsapp_id == m.whatsapp_id or g.wallet_address == m.address), None)

    registered = []
    for m in members:
        if m.address in voted:
            continue
        gm = group_entry(m)
        registered.append(
            RegisteredNonVoter(
                address=m.address,
                display_name=m.display_name,
                token_balance=m.token_balance,
                whatsapp_id=m.whatsapp_id or (gm.whatsapp_id if gm else None),
                is_on_whatsapp=gm is not None,
                last_active=aware(gm.last_seen) if gm else None,
            )
        )

    tracked = [
        TrackedNonVoter(
            whatsapp_id=g.whatsapp_id,
            display_name=g.display_name,
            wallet_address=g.wallet_address,
            message_count=g.message_count,
            last_active=aware(g.last_seen),
        )
        for g in group
        if g.whatsapp_id not in registered_ids and (g.wallet_address or "") not in voted
    ]

    return NonVoters(
        proposal_number=proposal_number,
        title=p.title,
        total_votes=len(votes),
        registered_non_voters=registered,
        tracked_whatsapp_non_voters=tracked,
        total_whatsapp_members=len(group),
    )
