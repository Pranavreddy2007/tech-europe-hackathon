import hashlib
import hmac
import json
import os
from types import SimpleNamespace

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


def test_tool_schemas_are_valid_for_claude():
    assert len(tools.ANTHROPIC_TOOLS) == 24
    for t in tools.ANTHROPIC_TOOLS:
        assert t["input_schema"]["type"] == "object"
        schema = t["input_schema"]
        assert set(schema.get("required", [])) <= set(schema["properties"])
        assert not isinstance(schema.get("title"), str)
    names = {t["name"] for t in tools.ANTHROPIC_TOOLS}
    assert {"send_group_message", "send_direct_message", "link_wallet"} <= names


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
    """Drive the loop with a fake Claude: one tool call, then a final answer."""
    sent = []

    class FakeWA:
        async def send_text(self, to, text):
            sent.append((to, text))
            return True

        async def send_image(self, to, link, caption=None):
            return True

    replies = iter([
        SimpleNamespace(stop_reason="tool_use", content=[
            SimpleNamespace(type="tool_use", id="t1", name="get_treasury_summary", input={}),
            SimpleNamespace(type="tool_use", id="t2", name="send_direct_message",
                            input={"text": "Runway is healthy"}),
        ]),
        SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Done")]),
    ])
    seen_messages = []

    async def fake_create(messages):
        seen_messages.append(list(messages))
        return next(replies)

    monkeypatch.setattr(runner, "_create", fake_create)
    monkeypatch.setattr(tools, "get_client", lambda: FakeWA())

    final = await runner.run("test", tools.RunContext(sender_id="447700900001"))
    assert final == "Done"
    assert sent == [("447700900001", "Runway is healthy")]
    tool_results = seen_messages[1][-1]["content"]
    assert [r["tool_use_id"] for r in tool_results] == ["t1", "t2"]
    assert json.loads(tool_results[0]["content"])["total_balance_eds"] == 142.3
