import hashlib
import hmac
import json
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_govmind.db"
os.environ["CHART_DIR"] = "./test_charts"
os.environ["WHATSAPP_ACCESS_TOKEN"] = ""
os.environ["WHATSAPP_APP_SECRET"] = "test-secret"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "verify-me"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from govmind.agent import runner, tools  # noqa: E402
from govmind.api import app  # noqa: E402
from govmind.seed import seed  # noqa: E402
from govmind.services import governance, knowledge, security, treasury  # noqa: E402
from govmind.whatsapp import handler  # noqa: E402
from govmind.whatsapp.models import WebhookPayload  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
async def seeded():
    await seed()
    yield
    os.remove("test_govmind.db")


def webhook_payload(text: str, msg_id: str = "wamid.1", sender: str = "447700900001") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550000000", "phone_number_id": "999"},
                    "contacts": [{"wa_id": sender, "profile": {"name": "Alice"}}],
                    "messages": [{"id": msg_id, "from": sender, "timestamp": "1", "type": "text",
                                  "text": {"body": text}}],
                },
            }],
        }],
    }


async def test_active_proposals_match_seed():
    active = await governance.get_active_proposals()
    assert [p.proposal_number for p in active] == [48, 49]
    p48 = active[0]
    assert p48.total_votes == 8 and p48.participation_rate == "17.0%"


async def test_attack_pattern_visible():
    transfers = await security.get_token_transfers(72)
    sources = [t.from_address for t in transfers if t.amount == 4000]
    assert len(sources) == 3 and len(set(sources)) == 1
    profile = await security.get_wallet_profile("0x" + "atk001".rjust(40, "0"))
    assert not profile.is_known_member and profile.wallet_age_days <= 1


async def test_treasury_summary():
    s = await treasury.get_treasury_summary()
    assert s.total_balance_eds == 142.3
    assert s.concentration_risk.risk_level == "HIGH"
    assert s.runway_months and s.runway_months > 0


async def test_query_data_is_read_only():
    ok = await knowledge.query_data("SELECT count(*) AS n FROM members")
    assert ok.rows[0]["n"] == 47
    blocked = await knowledge.query_data("DELETE FROM members")
    assert "error" in blocked.model_dump()
    stacked = await knowledge.query_data("SELECT 1; SELECT 2")
    assert "error" in stacked.model_dump()


async def test_vote_flow_and_non_voters():
    result = await governance.cast_vote(48, "0x" + "gen0001".rjust(40, "0"), "for")
    assert result.total_votes_now == 9
    again = await governance.cast_vote(48, "0x" + "gen0001".rjust(40, "0"), "for")
    assert "already voted" in again.error
    nv = await governance.get_non_voters(48)
    assert all(m.address != "0x" + "gen0001".rjust(40, "0") for m in nv.registered_non_voters)


def test_tool_schemas_are_valid():
    assert len(tools.TOOLS) == 24
    for spec in tools.TOOLS.values():
        schema = spec.json_schema()
        assert schema["type"] == "object"
        assert set(schema.get("required", [])) <= set(schema.get("properties", {}))
        assert not isinstance(schema.get("title"), str)
    assert {"send_group_message", "send_direct_message", "link_wallet"} <= set(tools.TOOLS)


async def test_tool_validation_rejects_bad_input():
    result, _, is_error = await tools.execute("cast_vote", {"proposal_number": 48, "voter_address": "x",
                                                            "vote": "maybe"}, tools.RunContext())
    assert is_error and "Invalid input" in result["error"]


def test_webhook_model_parses_text_and_list_replies():
    payload = WebhookPayload.model_validate(webhook_payload("hello"))
    [(msg, name)] = list(payload.iter_messages())
    assert msg.from_ == "447700900001" and name == "Alice" and msg.body == "hello"

    raw = webhook_payload("")
    raw["entry"][0]["changes"][0]["value"]["messages"][0] = {
        "id": "wamid.2", "from": "447700900001", "timestamp": "1", "type": "interactive",
        "interactive": {"type": "list_reply", "list_reply": {"id": "cmd_treasury", "title": "Treasury status"}},
    }
    [(msg, _)] = list(WebhookPayload.model_validate(raw).iter_messages())
    assert handler.message_text(msg) == "treasury status"


def test_wallet_extraction():
    assert handler.extract_wallet("my wallet is 4T1JmiB34KERKGVxUMNXXZJSRngzwWS5KTP4AcgtK2qf") is not None
    assert handler.extract_wallet("just a long word 4T1JmiB34KERKGVxUMNXXZJSRngzwWS5KTP4AcgtK2qf") is None


def test_webhook_verification_and_signature(monkeypatch):
    runs = []

    async def fake_handle(msg, name):
        runs.append((msg.body, name))

    monkeypatch.setattr("govmind.api.handle_message", fake_handle)
    with TestClient(app) as client:
        ok = client.get("/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me",
                                                     "hub.challenge": "42"})
        assert ok.status_code == 200 and ok.text == "42"
        bad = client.get("/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "nope",
                                                      "hub.challenge": "42"})
        assert bad.status_code == 403

        body = json.dumps(webhook_payload("what's our runway?")).encode()
        assert client.post("/webhook/whatsapp", content=body).status_code == 401
        sig = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        resp = client.post("/webhook/whatsapp", content=body, headers={"X-Hub-Signature-256": sig})
        assert resp.status_code == 200
        health = client.get("/api/health").json()
        assert len(health["proposals"]) == 2
    assert runs == [("what's our runway?", "Alice")]


async def test_agent_loop_replies_on_whatsapp(monkeypatch):
    """Drive the Pydantic AI agent with a scripted model: two parallel tool calls, then a final answer."""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
    from pydantic_ai.models.function import FunctionModel

    sent, emitted = [], []

    class FakeWA:
        async def send_text(self, to, text):
            sent.append((to, text))
            return True

        async def send_image(self, to, link, caption=None):
            return True

    seen = []

    def scripted(messages, info):
        seen.append(messages)
        if len(seen) == 1:
            assert {t.name for t in info.function_tools} == set(tools.TOOLS)
            return ModelResponse(parts=[
                ToolCallPart("get_treasury_summary", {}, tool_call_id="t1"),
                ToolCallPart("send_direct_message", {"text": "Runway is healthy"}, tool_call_id="t2"),
            ])
        return ModelResponse(parts=[TextPart("Done")])

    async def record(name, *args):
        emitted.append(name)

    monkeypatch.setattr(tools, "get_client", lambda: FakeWA())
    monkeypatch.setattr(runner.events, "tool_start", lambda tool, _: record(f"start:{tool}"))
    monkeypatch.setattr(runner.events, "tool_result", lambda tool, _: record(f"result:{tool}"))

    final = await runner.run("test", tools.RunContext(sender_id="447700900001"), model=FunctionModel(scripted))
    assert final == "Done"
    assert sent == [("447700900001", "Runway is healthy")]
    returns = {p.tool_call_id: p.content for p in seen[1][-1].parts if isinstance(p, ToolReturnPart)}
    assert json.loads(returns["t1"])["total_balance_eds"] == 142.3
    assert sorted(emitted) == sorted(["start:get_treasury_summary", "start:send_direct_message",
                                      "result:get_treasury_summary", "result:send_direct_message"])


async def test_bad_tool_args_are_reported_to_the_model():
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
    from pydantic_ai.models.function import FunctionModel

    seen = []

    def scripted(messages, info):
        seen.append(messages)
        if len(seen) == 1:
            return ModelResponse(parts=[ToolCallPart("get_proposal_detail", {"proposal_number": 999})])
        return ModelResponse(parts=[TextPart("not found")])

    assert await runner.run("x", model=FunctionModel(scripted)) == "not found"
    [ret] = [p for p in seen[1][-1].parts if isinstance(p, ToolReturnPart)]
    assert "not found" in ret.content
