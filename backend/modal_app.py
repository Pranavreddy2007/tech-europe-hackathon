"""Deploy GovMind to Modal.

    modal secret create govmind-secrets ANTHROPIC_API_KEY=... WHATSAPP_ACCESS_TOKEN=... \
        WHATSAPP_PHONE_NUMBER_ID=... WHATSAPP_VERIFY_TOKEN=... WHATSAPP_APP_SECRET=... \
        DATABASE_URL=postgresql://... ENDLESS_PRIVATE_KEY=...
    modal run modal_app.py::seed      # load the MetaDAO demo data
    modal deploy modal_app.py         # prints the web URL → register <url>/webhook/whatsapp with Meta
"""

import os
from pathlib import Path

import modal

HERE = Path(__file__).parent

app = modal.App("govmind")
data = modal.Volume.from_name("govmind-data", create_if_missing=True)
secrets = [modal.Secret.from_name("govmind-secrets")]

image = (
    modal.Image.debian_slim(python_version="3.12")
    # Node runs the Endless Chain signer (the chain only ships a TypeScript SDK).
    .apt_install("curl", "ca-certificates")
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
    )
    .add_local_file(HERE / "chain" / "package.json", "/root/chain/package.json", copy=True)
    .run_commands("cd /root/chain && npm install --omit=dev")
    .uv_pip_install(
        "anthropic>=1.7",
        "fastapi>=0.115",
        "pydantic>=2.8",
        "pydantic-settings>=2.4",
        "python-socketio>=5.11",
        "httpx>=0.27",
        "sqlalchemy[asyncio]>=2.0.30",
        "asyncpg>=0.29",
        "aiosqlite>=0.20",
        "matplotlib>=3.9",
    )
    .env({"CHAIN_HELPER_DIR": "/root/chain", "CHART_DIR": "/data/charts"})
    .add_local_file(HERE / "chain" / "endless.mjs", "/root/chain/endless.mjs")
    .add_local_python_source("govmind")
)


def _use_volume_db_if_unset() -> None:
    # Without a DATABASE_URL secret, fall back to SQLite on the persistent volume.
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////data/govmind.db")


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/data": data},
    # One container: Socket.IO dashboard clients and agent runs share in-process state.
    max_containers=1,
    scaledown_window=15 * 60,
    timeout=10 * 60,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def web():
    _use_volume_db_if_unset()
    from govmind.api import asgi_app

    return asgi_app


@app.function(image=image, secrets=secrets, volumes={"/data": data}, timeout=5 * 60)
async def seed():
    _use_volume_db_if_unset()
    from govmind.seed import seed as run_seed

    await run_seed()
    await data.commit.aio()


@app.function(image=image, secrets=secrets, schedule=modal.Cron("0 9 * * *"), timeout=15 * 60)
async def daily_sweep():
    """Every morning: attack scan + vote mobilisation. Opt in with SCHEDULED_CHECKS_ENABLED=true."""
    import httpx

    from govmind.config import get_settings

    if not get_settings().scheduled_checks_enabled:
        return
    # Run through the web container so the dashboard sees the runs live.
    base = await web.get_web_url.aio()
    async with httpx.AsyncClient(timeout=10 * 60, follow_redirects=True) as client:
        for check in ("attack-check", "vote-check"):
            (await client.post(f"{base}/trigger/{check}")).raise_for_status()
