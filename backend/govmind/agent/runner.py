"""The GovMind agent loop: a Pydantic AI agent on Gemini with 24 tools, streamed to the dashboard."""

import asyncio
import json
import logging
from typing import Any

from pydantic_ai import Agent, Tool, UsageLimits
from pydantic_ai.messages import FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.gateway import gateway_provider
from pydantic_ai.providers.google import GoogleProvider

from .. import events
from ..config import get_settings
from .prompt import SYSTEM_PROMPT
from .tools import TOOLS, RunContext, execute

log = logging.getLogger(__name__)

MAX_ITERATIONS = 30  # model requests; Gemini tends to call tools one at a time
TIMEOUT_S = 240
MAX_RESULT_CHARS = 2000

# One run at a time: the dashboard renders a single active run, and the
# original bot processed messages sequentially too.
_run_lock = asyncio.Lock()
_model: Model | None = None


def get_model() -> Model:
    global _model
    if _model is None:
        s = get_settings()
        if s.gemini_api_key:
            provider = GoogleProvider(api_key=s.gemini_api_key)
        elif s.pydantic_ai_gateway_api_key:
            provider = gateway_provider("google", api_key=s.pydantic_ai_gateway_api_key)
        else:
            raise RuntimeError("Set GEMINI_API_KEY (or PYDANTIC_AI_GATEWAY_API_KEY) to run the agent.")
        _model = GoogleModel(s.gemini_model, provider=provider)
    return _model


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


def _encode(result: Any) -> str:
    safe = truncate(result)
    encoded = safe if isinstance(safe, str) else json.dumps(safe, default=str)
    if len(encoded) > MAX_RESULT_CHARS:
        encoded = encoded[: MAX_RESULT_CHARS - 100] + '..."truncated"}'
    return encoded


def build_agent(ctx: RunContext, steps: list[dict], model: Model | None = None) -> Agent:
    """A fresh agent per run, so tool closures carry this run's WhatsApp context."""

    def make(name: str) -> Tool:
        spec = TOOLS[name]

        async def call(**kwargs: Any) -> str:
            result, description, _ = await execute(name, kwargs, ctx)
            steps.append({"tool": name, "input": kwargs, "output": truncate(result), "description": description})
            return _encode(result)

        return Tool.from_schema(
            call, name=name, description=spec.description, json_schema=spec.json_schema()
        )

    return Agent(
        model or get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[make(name) for name in TOOLS],
        retries=2,
    )


async def _stream_to_dashboard(stream) -> None:
    async for event in stream:
        if isinstance(event, FunctionToolCallEvent):
            await events.tool_start(event.part.tool_name, event.part.args_as_dict())
        elif isinstance(event, FunctionToolResultEvent):
            content = event.part.content
            try:
                content = json.loads(content) if isinstance(content, str) else content
            except ValueError:
                pass
            await events.tool_result(event.part.tool_name, content)


async def _drive(agent: Agent, prompt: str) -> str:
    """Step through the agent graph, streaming each tool call/result to the dashboard as it happens."""
    async with agent.iter(prompt, usage_limits=UsageLimits(request_limit=MAX_ITERATIONS)) as agent_run:
        async for node in agent_run:
            if Agent.is_call_tools_node(node):
                async with node.stream(agent_run.ctx) as stream:
                    await _stream_to_dashboard(stream)
    return agent_run.result.output


async def run(
    trigger: str, ctx: RunContext | None = None, history: list[str] | None = None, model: Model | None = None
) -> str:
    async with _run_lock:
        return await _run(trigger, ctx or RunContext(), history, model)


async def _run(trigger: str, ctx: RunContext, history: list[str] | None, model: Model | None) -> str:
    await events.agent_start(trigger)
    steps: list[dict] = []
    prompt = trigger
    if history:
        prompt = "Recent messages for context:\n" + "\n".join(history) + f"\n\n---\n\nCurrent task: {trigger}"

    try:
        output = await asyncio.wait_for(_drive(build_agent(ctx, steps, model), prompt), timeout=TIMEOUT_S)
        final = (output or "").strip() or "No response generated."
        await events.agent_complete(final, steps)
        return final
    except TimeoutError:
        msg = f"Agent loop timed out after {TIMEOUT_S} seconds."
    except Exception as err:  # any failure must still close the run on the dashboard
        log.exception("Agent run failed")
        msg = f"Agent error: {err}"
    await events.agent_error(msg)
    return msg
