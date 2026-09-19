"""The GovMind agent loop: Claude + 24 tools, streamed to the dashboard."""

import asyncio
import json
import logging
import time
from typing import Any

import anthropic

from .. import events
from ..config import get_settings
from .prompt import SYSTEM_PROMPT
from .tools import ANTHROPIC_TOOLS, RunContext, execute

log = logging.getLogger(__name__)

MAX_ITERATIONS = 15
TIMEOUT_S = 180
MAX_RESULT_CHARS = 2000

# One run at a time: the dashboard renders a single active run, and the
# original bot processed messages sequentially too.
_run_lock = asyncio.Lock()
_client: anthropic.AsyncAnthropic | None = None


def _anthropic() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key or None)
    return _client


def truncate(result: Any, depth: int = 0) -> Any:
    """Keep tool results small enough for the context window and the dashboard."""
    if result is None or isinstance(result, (bool, int, float)):
        return result
    if depth > 3:
        return "[nested]"
    if isinstance(result, str):
        return result if len(result) <= 300 else result[:300] + "..."
    if isinstance(result, list):
        limit = 10 if depth == 0 else 5
        items = [truncate(r, depth + 1) for r in result[:limit]]
        return items + [f"...({len(result) - limit} more)"] if len(result) > limit else items
    if isinstance(result, dict):
        return {k: truncate(v, depth + 1) for k, v in result.items()}
    return str(result)


def _text(content: list) -> str:
    return "\n".join(b.text for b in content if b.type == "text").strip()


async def _create(messages: list[dict]):
    settings = get_settings()
    params: dict[str, Any] = dict(
        model=settings.anthropic_model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=ANTHROPIC_TOOLS,
        messages=messages,
    )
    if settings.anthropic_model == "claude-opus-5":
        # On a policy decline, re-run server-side on Anthropic's recommended fallback model.
        return await _anthropic().beta.messages.create(
            **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
        )
    return await _anthropic().messages.create(**params)


async def run(trigger: str, ctx: RunContext | None = None, history: list[str] | None = None) -> str:
    async with _run_lock:
        return await _run(trigger, ctx or RunContext(), history)


async def _run(trigger: str, ctx: RunContext, history: list[str] | None) -> str:
    await events.agent_start(trigger)
    steps: list[dict] = []
    started = time.monotonic()
    content = trigger
    if history:
        content = "Recent messages for context:\n" + "\n".join(history) + f"\n\n---\n\nCurrent task: {trigger}"
    messages: list[dict] = [{"role": "user", "content": content}]

    try:
        for _ in range(MAX_ITERATIONS):
            if time.monotonic() - started > TIMEOUT_S:
                msg = f"Agent loop timed out after {TIMEOUT_S} seconds."
                await events.agent_error(msg)
                return msg

            response = await _create(messages)

            if response.stop_reason == "refusal":
                msg = "GovMind declined this request."
                await events.agent_error(msg)
                return msg

            if response.stop_reason != "tool_use":
                final = _text(response.content) or "No response generated."
                await events.agent_complete(final, steps)
                return final

            messages.append({"role": "assistant", "content": response.content})
            calls = [b for b in response.content if b.type == "tool_use"]
            for call in calls:
                await events.tool_start(call.name, call.input)

            outcomes = await asyncio.gather(*(execute(c.name, c.input, ctx) for c in calls))

            tool_results = []
            for call, (result, description, is_error) in zip(calls, outcomes):
                safe = truncate(result)
                encoded = safe if isinstance(safe, str) else json.dumps(safe, default=str)
                if len(encoded) > MAX_RESULT_CHARS:
                    encoded = encoded[: MAX_RESULT_CHARS - 100] + '..."truncated"}'
                steps.append({"tool": call.name, "input": call.input, "output": safe, "description": description})
                await events.tool_result(call.name, safe)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": call.id, "content": encoded, "is_error": is_error}
                )
            # All results for one assistant turn go back in a single user message.
            messages.append({"role": "user", "content": tool_results})

        msg = f"Agent reached maximum iterations ({MAX_ITERATIONS}) without producing a final response."
        await events.agent_error(msg)
        return msg
    except Exception as err:  # any failure must still close the run on the dashboard
        msg = f"Agent error: {err}"
        log.exception("Agent run failed")
        await events.agent_error(msg)
        return msg
