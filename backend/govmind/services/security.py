from datetime import timedelta

from sqlalchemy import or_, select

from ..db import Member, TokenTransfer, aware, session_scope, utcnow
from ..schemas import TransferOut, WalletProfile


def _out(t: TokenTransfer) -> TransferOut:
    return TransferOut(
        from_address=t.from_address, to_address=t.to_address, amount=t.amount, timestamp=aware(t.timestamp)
    )


async def get_token_transfers(hours_back: int = 48) -> list[TransferOut]:
    since = utcnow() - timedelta(hours=hours_back)
    async with session_scope() as s:
        rows = (
            await s.scalars(
                select(TokenTransfer).where(TokenTransfer.timestamp > since).order_by(TokenTransfer.timestamp.desc())
            )
        ).all()
    return [_out(t) for t in rows]


async def get_wallet_profile(address: str) -> WalletProfile:
    async with session_scope() as s:
        member = await s.scalar(select(Member).where(Member.address == address))
        transfers = list(
            (
                await s.scalars(
                    select(TokenTransfer)
                    .where(or_(TokenTransfer.from_address == address, TokenTransfer.to_address == address))
                    .order_by(TokenTransfer.timestamp.desc())
                )
            ).all()
        )

    sent = [t for t in transfers if t.from_address == address]
    received = [t for t in transfers if t.to_address == address]
    first = aware(transfers[-1].timestamp) if transfers else None

    return WalletProfile(
        address=address,
        is_known_member=member is not None,
        display_name=member.display_name if member else None,
        token_balance=member.token_balance if member else 0,
        join_date=aware(member.join_date) if member else None,
        wallet_age_days=(utcnow() - first).days if first else 0,
        first_activity=first,
        total_transfers=len(transfers),
        sent_count=len(sent),
        received_count=len(received),
        total_sent=sum(t.amount for t in sent),
        total_received=sum(t.amount for t in received),
        recent_transfers=[_out(t) for t in transfers[:10]],
    )
