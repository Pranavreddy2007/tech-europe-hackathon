from datetime import timedelta

from sqlalchemy import select

from ..db import TreasuryBalance, TreasuryTransaction, aware, session_scope, utcnow
from ..schemas import Allocation, ConcentrationRisk, Direction, TreasurySummary, TreasuryTx


async def get_burn_rate() -> float:
    since = utcnow() - timedelta(days=30)
    async with session_scope() as s:
        outflows = (
            await s.scalars(
                select(TreasuryTransaction.amount).where(
                    TreasuryTransaction.direction == "outflow", TreasuryTransaction.timestamp > since
                )
            )
        ).all()
    return float(sum(outflows))


def _concentration(balances: list[TreasuryBalance]) -> ConcentrationRisk:
    if not balances or sum(b.usd_value for b in balances) == 0:
        return ConcentrationRisk(risk_level="unknown", details="No treasury data")
    dominant = max(balances, key=lambda b: b.percentage)
    pct = dominant.percentage
    if pct >= 80:
        return ConcentrationRisk(
            risk_level="HIGH",
            details=f"{pct:g}% concentrated in {dominant.token}. A 30% price drop would reduce runway significantly.",
        )
    if pct >= 60:
        return ConcentrationRisk(
            risk_level="MEDIUM", details=f"{pct:g}% in {dominant.token}. Some diversification recommended."
        )
    return ConcentrationRisk(risk_level="LOW", details="Treasury is reasonably diversified.")


async def get_treasury_summary() -> TreasurySummary:
    async with session_scope() as s:
        balances = list((await s.scalars(select(TreasuryBalance))).all())
    total_eds = sum(b.balance for b in balances)
    burn = await get_burn_rate()
    return TreasurySummary(
        total_balance_eds=round(total_eds, 2),
        total_balance_usd=round(sum(b.usd_value for b in balances), 2),
        allocations=[Allocation.model_validate(b) for b in balances],
        monthly_burn_rate_eds=round(burn, 2),
        runway_months=round(total_eds / burn, 1) if burn > 0 else None,
        concentration_risk=_concentration(balances),
    )


async def get_transactions(
    direction: Direction | None = None,
    category: str | None = None,
    days_back: int | None = None,
    limit: int | None = None,
) -> list[TreasuryTx]:
    q = select(TreasuryTransaction)
    if direction:
        q = q.where(TreasuryTransaction.direction == direction)
    if category:
        q = q.where(TreasuryTransaction.category == category)
    if days_back:
        q = q.where(TreasuryTransaction.timestamp > utcnow() - timedelta(days=days_back))
    q = q.order_by(TreasuryTransaction.timestamp.desc())
    if limit:
        q = q.limit(limit)
    async with session_scope() as s:
        rows = (await s.scalars(q)).all()
    return [TreasuryTx.model_validate(r).model_copy(update={"timestamp": aware(r.timestamp)}) for r in rows]
