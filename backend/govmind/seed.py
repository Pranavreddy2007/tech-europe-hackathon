"""Seed MetaDAO demo data: 47 members, 10 proposals, treasury history, and an attack pattern.

    python -m govmind.seed
"""

import asyncio
import random
from datetime import timedelta

from sqlalchemy import delete

from .db import (
    AgentAction,
    Knowledge,
    Member,
    NudgeTracking,
    Proposal,
    TokenTransfer,
    TreasuryBalance,
    TreasuryTransaction,
    Vote,
    engine,
    init_db,
    session_scope,
    utcnow,
)

NOW = utcnow()


def days_ago(n: float):
    return NOW - timedelta(days=n)


def hours_ago(n: float):
    return NOW - timedelta(hours=n)


def addr(suffix: str) -> str:
    return "0x" + suffix.rjust(40, "0")


def tx_hash(i: int) -> str:
    return "0x" + format(i, "x").rjust(64, "a")


# First 5 members have WhatsApp IDs so vote nudges have someone to message.
# Replace them with your team's real numbers (digits only, with country code) for a live demo.
CORE_MEMBERS = [
    ("Alice Chen", "7f3a1", 8500, 18, "447700900001"),
    ("Bob Martinez", "8b2c4", 6200, 16, "447700900002"),
    ("Carol Wei", "3d9e7", 5100, 15, "447700900003"),
    ("David Okonkwo", "a1f5b", 4300, 14, "447700900004"),
    ("Elena Popov", "c6d2a", 3800, 12, "447700900005"),
    ("Frank Liu", "e4b38", 3200, 11, None),
    ("Grace Kim", "f7c91", 2800, 10, None),
    ("Hassan Ali", "12d4e", 2500, 10, None),
    ("Isha Patel", "23e5f", 2200, 9, None),
    ("Jake Thompson", "34f60", 1900, 8, None),
    ("Keiko Tanaka", "45071", 1700, 8, None),
    ("Liam Murphy", "56182", 1500, 7, None),
    ("Maya Singh", "67293", 1300, 7, None),
    ("Noah Andersen", "783a4", 1100, 6, None),
    ("Olivia Brown", "894b5", 950, 6, None),
]

GENERAL_NAMES = [
    "Peter Vu", "Quinn Roberts", "Rita Fernandez", "Sam Jackson", "Tina Zhao",
    "Uma Kapoor", "Victor Novak", "Wendy Chang", "Xavier Reis", "Yuki Sato",
    "Zara Ahmed", "Aaron Cole", "Bianca Rossi", "Carlos Diaz", "Diana Lee",
    "Ethan Brooks", "Fatima Noor", "George Park", "Hana Müller", "Ian Stewart",
    "Julia Costa", "Kevin Wright", "Luna Garcia", "Marcus Hahn", "Nadia Ivanova",
    "Oscar Tran", "Paula Schmidt", "Ryan Choi", "Sofia Morales", "Tom Fischer",
    "Ursula Katz", "Wei Zhang",
]
GENERAL_MEMBERS = [
    (name, f"gen{i + 1:04d}", 200 + (800 * (len(GENERAL_NAMES) - i)) // len(GENERAL_NAMES), 1 + i % 6, None)
    for i, name in enumerate(GENERAL_NAMES)
]

# (number, title, body, proposer suffix, amount, recipient, status, start days ago, end days ago, end days from now)
PROPOSALS = [
    (40, "Upgrade Smart Contract Auditor Retainer",
     "Proposal to renew our smart contract auditing retainer with OpenZeppelin for another 6 months. Current coverage expires April 15. Cost: 12 EDS for the 6-month engagement, covering up to 3 audit cycles on our governance and treasury contracts.",
     "7f3a1", 12, addr("audit01"), "executed", 90, 83, None),
    (41, "Community Developer Bounty Program",
     "Launch a developer bounty program to incentivize external contributors. 20 EDS allocated across 40 bounties ranging from bug fixes (0.1 EDS) to feature development (2 EDS). Program runs for 3 months with monthly progress reports.",
     "8b2c4", 20, addr("bounty01"), "passed", 75, 68, None),
    (42, "Treasury Diversification: Convert 30 EDS to USDC",
     "Convert 30 EDS from the treasury to USDC to reduce volatility exposure. Current treasury is 89% in GOV token, which creates concentration risk. This conversion would bring stablecoin allocation to ~25%.",
     "3d9e7", 0, None, "passed", 60, 53, None),
    (43, "Hire Full-Time Protocol Engineer",
     "Hire a full-time protocol engineer at 5 EDS/month for 6 months (30 EDS total). The candidate has been a top bounty contributor and has shipped 3 protocol improvements. This would be our first full-time technical hire.",
     "7f3a1", 30, addr("hire01"), "passed", 50, 43, None),
    (44, "Governance Parameter Update: Quorum to 15%",
     "Lower the governance quorum requirement from 20% to 15% of token-weighted votes. Current 20% threshold is rarely met, causing important proposals to fail due to apathy rather than opposition. Analysis of last 20 proposals shows average participation of 22% — too close to quorum.",
     "a1f5b", 0, None, "rejected", 40, 33, None),
    (45, "Sponsor Endless Hackathon — Bronze Tier",
     "Sponsor the next Endless hackathon at Bronze tier (8 EDS). Gets us a booth, logo placement, and access to the builder community. Potential to recruit contributors and raise awareness of MetaDAO governance tooling.",
     "c6d2a", 8, addr("sponsor01"), "passed", 30, 23, None),
    (46, "Emergency Bug Bounty: Critical Vulnerability",
     "Retroactive bug bounty payment of 15 EDS to white hat researcher who discovered a critical reentrancy vulnerability in our staking contract. Vulnerability was responsibly disclosed and patched within 4 hours. This payment follows our published bug bounty guidelines.",
     "7f3a1", 15, addr("whitehat01"), "executed", 20, 15, None),
    (47, "Create DAO Legal Wrapper (Cayman Foundation)",
     "Establish a Cayman Islands foundation as the legal wrapper for MetaDAO. Cost: 10 EDS for legal fees plus 2 EDS annual maintenance. This provides legal standing for the DAO to enter contracts, hold IP, and interact with traditional financial institutions.",
     "e4b38", 10, addr("legal01"), "cancelled", 15, 10, None),
    # Active proposals for the demo
    (48, "Fund Marketing Sprint Q2",
     "Requests 45 EDS ($90,000) from treasury to fund a 3-month marketing campaign targeting DeFi users. Deliverables include: redesigned landing page, Twitter/X content strategy (3 posts/week), sponsorship of 2 DeFi podcasts, and a referral program with $GOV token incentives. Success metrics: 500 new token holders, 2x governance participation, 10k unique site visitors/month.",
     "7f3a1", 45, addr("marketing01"), "active", 3, None, 4),
    (49, "Strategic Partnership Fund Transfer",
     'Transfer 80 EDS to external wallet 0x9e2b...unknown for a "strategic partnership" with an unnamed DeFi protocol. The proposer claims this will provide liquidity incentives and cross-promotion. No specific milestones, deliverables, or success metrics provided. Funds would be sent in a single transaction with no vesting or clawback mechanism.',
     "9e2b0", 80, addr("9e2b0drain"), "active", 1, None, 6),
]

# (direction, amount, token, category, memo, days ago)
TREASURY_TXS = [
    ("inflow", 15.0, "EDS", "revenue", "Protocol fees — January", 150),
    ("inflow", 18.5, "EDS", "revenue", "Protocol fees — February", 120),
    ("inflow", 12.0, "EDS", "revenue", "Protocol fees — March", 90),
    ("inflow", 22.0, "EDS", "revenue", "Protocol fees — April", 60),
    ("inflow", 16.3, "EDS", "revenue", "Protocol fees — May", 30),
    ("inflow", 8.7, "EDS", "revenue", "Protocol fees — June (partial)", 5),
    ("inflow", 50.0, "EDS", "grant", "Endless Foundation grant", 140),
    *[("outflow", 5.0, "EDS", "contributor_payment", "Alice Chen — core contributor monthly", d) for d in (145, 115, 85, 55, 25)],
    *[("outflow", 3.5, "EDS", "contributor_payment", "Bob Martinez — dev lead monthly", d) for d in (145, 115, 85, 55, 25)],
    *[("outflow", 2.0, "EDS", "contributor_payment", "Carol Wei — ops monthly", d) for d in (115, 85, 55, 25)],
    ("outflow", 12.0, "EDS", "grant", "Proposal #40 — OpenZeppelin audit retainer", 82),
    ("outflow", 20.0, "EDS", "grant", "Proposal #41 — Developer bounty program", 67),
    ("outflow", 8.0, "EDS", "grant", "Proposal #45 — Endless hackathon sponsorship", 22),
    ("outflow", 15.0, "EDS", "grant", "Proposal #46 — Bug bounty payout", 14),
    ("outflow", 30.0, "EDS", "swap", "Proposal #42 — Treasury diversification to USDC", 52),
    ("inflow", 30.0, "USDC", "swap", "Received USDC from diversification swap", 52),
    # Recent bounty payouts drive up the burn rate
    ("outflow", 1.5, "EDS", "grant", "Bounty: Fix token approval UI", 18),
    ("outflow", 2.0, "EDS", "grant", "Bounty: Implement delegation", 12),
    ("outflow", 0.8, "EDS", "grant", "Bounty: Fix staking edge case", 8),
    ("outflow", 1.2, "EDS", "grant", "Bounty: Add vote delegation UI", 4),
    ("outflow", 0.5, "EDS", "grant", "Bounty: Documentation updates", 2),
    # New outflow category — should trigger an alert
    ("outflow", 3.0, "EDS", "infrastructure", "Cloud hosting upgrade — RPC nodes", 10),
    ("outflow", 1.8, "EDS", "infrastructure", "Monitoring and alerting services", 6),
    # Single large transaction to flag
    ("outflow", 18.0, "EDS", "grant", "Proposal #46 — Additional bug bounty reserve", 3),
]


async def seed() -> None:
    await init_db()
    async with session_scope() as s:
        for model in (NudgeTracking, Vote, TokenTransfer, TreasuryTransaction, TreasuryBalance, Knowledge,
                      AgentAction, Proposal, Member):
            await s.execute(delete(model))

        members = [
            Member(address=addr(suffix), display_name=name, token_balance=balance,
                   join_date=days_ago(months * 30), whatsapp_id=wa_id)
            for name, suffix, balance, months, wa_id in CORE_MEMBERS + GENERAL_MEMBERS
        ]
        s.add_all(members)

        proposals = [
            Proposal(proposal_number=num, title=title, body=body, proposer_address=addr(proposer),
                     requested_amount=amount, recipient_address=recipient, status=status,
                     vote_start=days_ago(start), created_at=days_ago(start),
                     vote_end=days_ago(end_ago) if end_ago is not None else NOW + timedelta(days=end_ahead))
            for num, title, body, proposer, amount, recipient, status, start, end_ago, end_ahead in PROPOSALS
        ]
        s.add_all(proposals)
        await s.flush()

        votes = []
        for p in proposals:
            if p.status == "cancelled":
                continue
            if p.proposal_number == 48:  # only 8 of 47 voted (17% participation)
                pool, for_ratio = members[:8], 0.6
            elif p.proposal_number == 49:  # attack proposal: 2 real members voted against
                pool, for_ratio = members[:2], 0.0
            elif p.status == "rejected":
                pool, for_ratio = members[: int(len(members) * 0.35)], 0.35
            else:
                pool = members[: int(len(members) * (0.3 + random.random() * 0.35))]
                for_ratio = 0.6 + random.random() * 0.25
            span = (p.vote_end - p.vote_start).total_seconds()
            for i, m in enumerate(pool):
                if i / len(pool) < for_ratio:
                    choice = "for"
                else:
                    choice = "abstain" if random.random() < 0.15 else "against"
                votes.append(Vote(proposal_id=p.id, voter_address=m.address, vote=choice,
                                  voting_power=m.token_balance,
                                  voted_at=p.vote_start + timedelta(seconds=random.random() * span)))
            if p.proposal_number == 49:  # three freshly funded wallets vote "for"
                for wallet in ("atk001", "atk002", "atk003"):
                    votes.append(Vote(proposal_id=p.id, voter_address=addr(wallet), vote="for",
                                      voting_power=4000, voted_at=hours_ago(2 + random.randint(0, 5))))
        s.add_all(votes)

        s.add_all([
            TreasuryBalance(token="GOV", balance=116.5, usd_value=233000, percentage=82),
            TreasuryBalance(token="USDC", balance=18.2, usd_value=36400, percentage=13),
            TreasuryBalance(token="DAI", balance=7.6, usd_value=15200, percentage=5),
        ])

        s.add_all([
            TreasuryTransaction(tx_hash=tx_hash(i + 1), direction=d, amount=amt, token=tok,
                                counterparty=addr(f"cp{i + 2}"), category=cat, memo=memo, timestamp=days_ago(ago))
            for i, (d, amt, tok, cat, memo, ago) in enumerate(TREASURY_TXS)
        ])

        source, proposer49 = addr("srcatk"), addr("9e2b0")
        attack_wallets = [addr("atk001"), addr("atk002"), addr("atk003")]
        transfers = [
            TokenTransfer(from_address=addr(a), to_address=addr(b), amount=amt, timestamp=hours_ago(h))
            for a, b, amt, h in [("7f3a1", "8b2c4", 200, 480), ("3d9e7", "a1f5b", 150, 360),
                                 ("e4b38", "f7c91", 100, 240), ("12d4e", "23e5f", 80, 120),
                                 ("34f60", "45071", 50, 72)]
        ]
        # Attack: an exchange-funded source wallet funds the #49 proposer and three fresh voting wallets.
        transfers += [
            TokenTransfer(from_address=addr("exchange01"), to_address=source, amount=15000, timestamp=hours_ago(48)),
            TokenTransfer(from_address=source, to_address=proposer49, amount=2500, timestamp=hours_ago(40)),
            *[TokenTransfer(from_address=source, to_address=w, amount=4000, timestamp=hours_ago(22 - i * 2))
              for i, w in enumerate(attack_wallets)],
            TokenTransfer(from_address=proposer49, to_address=attack_wallets[0], amount=500, timestamp=hours_ago(16)),
        ]
        s.add_all(transfers)

    print(f"Seeded {len(members)} members, {len(proposals)} proposals, {len(votes)} votes, "
          f"{len(TREASURY_TXS)} treasury transactions, {len(transfers)} token transfers.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
