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

import httpx

from ..config import get_settings
from ..schemas import AuditRecord, Balance, TransferResult

log = logging.getLogger(__name__)


class ChainError(RuntimeError):
    pass


RPC = {"mainnet": "https://rpc.endless.link/v1", "testnet": "https://rpc-test.endless.link/v1"}
_reachable: tuple[float, bool] = (0.0, True)
_down_until = 0.0  # circuit breaker: set when a real chain call times out
BREAKER_S = 15 * 60


async def _rpc_reachable() -> bool:
    """Cheap, cached reachability check so an Endless outage fails in seconds instead of stalling the agent."""
    global _reachable
    if time.monotonic() < _down_until:
        return False
    checked_at, ok = _reachable
    if time.monotonic() - checked_at < 60:
        return ok
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            ok = (await client.get(RPC.get(get_settings().endless_network, RPC["testnet"]))).status_code < 500
    except httpx.HTTPError:
        ok = False
    _reachable = (time.monotonic(), ok)
    if not ok:
        log.warning("Endless RPC unreachable; on-chain calls will fail fast for 60s")
    return ok


async def _run(*args: str) -> dict:
    global _down_until
    if not await _rpc_reachable():
        raise ChainError("Endless Chain RPC is unreachable right now (network outage); on-chain step skipped")
    settings = get_settings()
    env = {
        **os.environ,
        "ENDLESS_NETWORK": settings.endless_network,
        "ENDLESS_PRIVATE_KEY": settings.endless_private_key,
        "ENDLESS_KEY_FILE": str(settings.endless_key_file),
    }
    proc = await asyncio.create_subprocess_exec(
        "node",
        str(settings.chain_helper_dir / "endless.mjs"),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=25)
    except TimeoutError:
        proc.kill()
        # The RPC can answer health checks while real calls hang; stop trying for a while so
        # agent runs stay fast (a demo run must never stall on the chain).
        _down_until = time.monotonic() + BREAKER_S
        log.warning("Endless call timed out; skipping on-chain steps for %d min", BREAKER_S // 60)
        raise ChainError("Endless Chain call timed out") from None
    if proc.returncode != 0:
        raise ChainError(stderr.decode().strip().splitlines()[-1] if stderr else "chain helper failed")
    return json.loads(stdout)


def _explorer(tx_hash: str) -> str:
    return f"{get_settings().explorer_base}/txn/{tx_hash}"


async def warm_up() -> None:
    """Probe the chain in the background (startup / demo reset) so an outage trips the breaker early."""
    try:
        account = await agent_account()
        log.info("Endless agent account %s (%.4f EDS)", account["address"], account["balance_eds"])
    except Exception as err:
        log.warning("Endless warm-up failed: %s", err)


async def agent_account() -> dict:
    """The agent's own Endless account (auto-created and faucet-funded on testnet if needed)."""
    data = await _run("address")
    return {
        "address": data["address"],
        "balance_eds": int(data["balance_raw"]) / 1e8,
        "network": get_settings().endless_network,
        "explorer_url": f"{get_settings().explorer_base}/account/{data['address']}",
    }


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
