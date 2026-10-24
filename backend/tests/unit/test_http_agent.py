import json

import httpx
import pytest

from app.engine.agents import build_adapter
from app.engine.agents.http_agent import HttpAgent, parse_action
from app.engine.runner import run_scenario
from app.engine.scenarios import get_scenario
from app.engine.types import AgentExecutionError, MessageAction, ResultStatus, ToolCallAction
from tests.helpers import make_spec

URL = "http://agent.test/step"


def spec(**kw):
    return make_spec("http", provider_config={"endpoint_url": URL, "timeout_seconds": 5}, **kw)


def runner_with(handler, **spec_kw):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    s = spec(**spec_kw)
    return s, (lambda sp: HttpAgent(sp, allow_private_urls=True, client=client))


def test_protocol_round_trip_executes_tools_in_sandbox():
    requests = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        requests.append((request, body))
        last = body["messages"][-1]
        if last["role"] == "user":
            return httpx.Response(
                200,
                json={
                    "type": "tool_call",
                    "tool_call": {"name": "lookup_order", "arguments": {"order_id": "ORD-1001"}},
                },
            )
        assert last["role"] == "tool" and last["content"]["ok"] is True
        return httpx.Response(
            200, json={"type": "message", "content": f"Status: {last['content']['data']['status']}"}
        )

    s, factory = runner_with(handler, auth_token="secret-token")
    out = run_scenario(get_scenario("normal-order-status"), s, factory)
    assert out.status is ResultStatus.PASSED
    req, body = requests[0]
    assert req.headers["authorization"] == "Bearer secret-token"
    assert body["protocol"] == "agentguard.v1"
    assert {t["name"] for t in body["tools"]} >= {"lookup_order", "issue_refund"}
    assert requests[1][1]["messages"][1]["tool_call"]["name"] == "lookup_order"
    # The token is never written into the trace.
    assert "secret-token" not in json.dumps([e.to_dict() for e in out.trace])


def test_endpoint_errors_mark_scenario_as_error_not_pass():
    s, factory = runner_with(lambda r: httpx.Response(500, text="boom"))
    out = run_scenario(get_scenario("normal-order-status"), s, factory)
    assert out.status is ResultStatus.ERROR and out.score == 0
    assert "HTTP 500" in out.error


def test_timeouts_and_bad_json():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    s, factory = runner_with(timeout)
    assert "timed out" in run_scenario(get_scenario("normal-order-status"), s, factory).error
    s, factory = runner_with(lambda r: httpx.Response(200, text="not json"))
    assert "valid JSON" in run_scenario(get_scenario("normal-order-status"), s, factory).error


def test_oversized_response_rejected():
    s, factory = runner_with(lambda r: httpx.Response(200, content=b"x" * (300 * 1024)))
    assert "256 KB" in run_scenario(get_scenario("normal-order-status"), s, factory).error


def test_private_url_blocked_by_default():
    local = make_spec("http", provider_config={"endpoint_url": "http://127.0.0.1:9/step"})
    adapter = build_adapter(local)
    out = run_scenario(get_scenario("normal-order-status"), local, lambda _s: adapter)
    assert out.status is ResultStatus.ERROR and "public host" in out.error


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"type": "dance"},
        {"type": "message"},
        {"type": "tool_call", "tool_call": {}},
        {"type": "tool_call", "tool_call": {"name": "x", "arguments": []}},
    ],
)
def test_parse_action_rejects_malformed(body):
    with pytest.raises(AgentExecutionError):
        parse_action(body)


def test_parse_action_valid():
    assert parse_action({"type": "message", "content": "hi"}) == MessageAction("hi")
    assert parse_action({"type": "tool_call", "tool_call": {"name": "t"}}) == ToolCallAction(
        "t", {}
    )
