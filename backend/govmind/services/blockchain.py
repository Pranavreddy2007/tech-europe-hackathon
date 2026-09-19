"""Endless Chain operations.

Endless only ships a TypeScript SDK, so signing and submitting transactions is
delegated to `chain/endless.mjs` (Node is baked into the Modal image). This
module validates inputs/outputs with Pydantic and exposes plain async calls.
"""

import asyncio
import hashlib
import json
import logging
import os
import time

from ..config import get_settings
from ..schemas import AuditRecord, Balance, TransferResult

log = logging.getLogger(__name__)


class ChainError(RuntimeError):
    pass


async def _run(*args: str) -> dict:
    settings = get_settings()
    env = {**os.environ, "ENDLESS_NETWORK": settings.endless_network, "ENDLESS_PRIVATE_KEY": settings.endless_private_key}
    proc = await asyncio.create_subprocess_exec(
        "node",
        str(settings.chain_helper_dir / "endless.mjs"),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90)
    except TimeoutError:
        proc.kill()
        raise ChainError("Endless Chain call timed out") from None
    if proc.returncode != 0:
        raise ChainError(stderr.decode().strip().splitlines()[-1] if stderr else "chain helper failed")
    return json.loads(stdout)


def _explorer(tx_hash: str) -> str:
    return f"{get_settings().explorer_base}/txn/{tx_hash}"


async def get_balance(address: str) -> Balance:
    data = await _run("balance", address)
    raw = str(data["balance_raw"])
    return Balance(address=address, balance_eds=int(raw) / 1e8, balance_raw=raw, network=get_settings().endless_network)


async def transfer_eds(recipient_address: str, amount_eds: float) -> TransferResult:
    data = await _run("transfer", recipient_address, str(int(amount_eds * 1e8)))
    return TransferResult(
        success=data.get("success", True),
        tx_hash=data["tx_hash"],
        sender=data["sender"],
        recipient=recipient_address,
        amount_eds=amount_eds,
        network=get_settings().endless_network,
        explorer_url=_explorer(data["tx_hash"]),
    )


async def record_audit_trail(action_type: str, summary: str) -> AuditRecord:
    """Write a 1-octa self-transfer so the action has a verifiable on-chain timestamp."""
    digest = "0x" + hashlib.sha256(f"{action_type}:{summary}:{time.time()}".encode()).hexdigest()
    data = await _run("audit")
    return AuditRecord(
        success=True,
        tx_hash=data["tx_hash"],
        action_type=action_type,
        summary_hash=digest,
        network=get_settings().endless_network,
        explorer_url=_explorer(data["tx_hash"]),
    )
