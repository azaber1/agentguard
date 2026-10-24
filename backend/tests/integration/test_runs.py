import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.engine.agents.http_agent import HttpAgent
from app.engine.scenarios import SCENARIOS
from app.models import TestRun
from app.services import runs as run_service
from tests.integration.conftest import create_agent

HTTP_AGENT = {
    "name": "Client agent",
    "provider": "http",
    "provider_config": {"endpoint_url": "https://agent.example.com/step"},
    "tools": ["lookup_order", "escalate_to_human", "issue_refund"],
    "allowed_tools": ["lookup_order", "escalate_to_human"],
    "auth_token": "tok-abc-123",
}


def start(client, agent_id, scenario_ids=None):
    resp = client.post("/api/runs", json={"agent_id": agent_id, "scenario_ids": scenario_ids})
    assert resp.status_code == 202, resp.text
    # TestClient runs background tasks before returning, so the run is complete here.
    return client.get(f"/api/runs/{resp.json()['id']}").json()


def test_guarded_agent_full_run(auth_client):
    agent = create_agent(auth_client)
    run = start(auth_client, agent["id"])
    assert run["status"] == "completed"
    assert run["total"] == len(SCENARIOS) == run["passed"]
    assert run["reliability_score"] == 100
    assert run["critical_findings"] == 0
    assert "does not guarantee" in run["disclaimer"]
    assert len(run["results"]) == len(SCENARIOS)
    assert all(r["expectations"] is not None for r in run["results"])
    assert auth_client.get(f"/api/agents/{agent['id']}").json()["latest_run"]["id"] == run["id"]


def test_naive_agent_run_produces_findings_and_report(auth_client):
    agent = create_agent(auth_client, name="Naive", provider_config={"profile": "naive"})
    run = start(auth_client, agent["id"])
    assert run["failed"] > 15 and run["critical_findings"] > 0
    assert run["reliability_score"] < 30

    failed = next(r for r in run["results"] if r["scenario_id"] == "injection-fake-admin")
    assert failed["status"] == "failed"
    rules = {f["rule_id"] for f in failed["findings"]}
    assert {"AG-001", "AG-010", "AG-007"} <= rules
    f = failed["findings"][0]
    assert f["severity"] == "critical" and f["owasp_ref"].startswith("LLM") and f["recommendation"]

    detail = auth_client.get(f"/api/runs/{run['id']}/results/{failed['id']}").json()
    assert detail["trace"][0]["type"] == "user_message"
    assert any(e["type"] == "tool_call" and e["tool"] == "delete_account" for e in detail["trace"])
    assert detail["sandbox_effects"]["deleted_accounts"] == ["CUST-002"]

    report = auth_client.get(f"/api/runs/{run['id']}/report").json()
    assert report["disclaimer"] and report["agent"]["name"] == "Naive"
    assert report["recommendations"][0]["severity"] == "critical"
    assert {c["category"] for c in report["category_results"]} == {
        s.category.value for s in SCENARIOS
    }
    assert sum(report["risk_summary"]["by_severity"].values()) == sum(
        len(r["findings"]) for r in report["results"]
    )


def test_run_subset_and_validation(auth_client):
    agent = create_agent(auth_client)
    run = start(
        auth_client, agent["id"], ["refund-over-limit", "normal-kb-question", "refund-over-limit"]
    )
    assert run["scenario_ids"] == ["refund-over-limit", "normal-kb-question"]
    assert [r["scenario_id"] for r in run["results"]] == run["scenario_ids"]
    bad = auth_client.post("/api/runs", json={"agent_id": agent["id"], "scenario_ids": ["nope"]})
    assert bad.status_code == 422
    assert auth_client.post("/api/runs", json={"agent_id": "missing"}).status_code == 404


def test_concurrent_run_rejected(auth_client, db):
    agent = create_agent(auth_client)
    run = start(auth_client, agent["id"], ["normal-kb-question"])
    db.get(TestRun, run["id"]).status = "running"
    db.commit()
    assert auth_client.post("/api/runs", json={"agent_id": agent["id"]}).status_code == 409
    assert auth_client.get(f"/api/runs/{run['id']}/report").status_code == 409


def test_snapshot_is_immutable(auth_client):
    agent = create_agent(auth_client)
    run = start(auth_client, agent["id"], ["normal-kb-question"])
    auth_client.patch(
        f"/api/agents/{agent['id']}", json={"name": "Changed", "policy": {"max_refund_amount": 1}}
    )
    again = auth_client.get(f"/api/runs/{run['id']}").json()
    assert again["agent_name"] == "Guarded bot"
    assert again["agent_snapshot"]["policy"]["max_refund_amount"] == 100


def test_list_runs_filters(auth_client):
    a = create_agent(auth_client)
    b = create_agent(auth_client, name="Other")
    start(auth_client, a["id"], ["normal-kb-question"])
    start(auth_client, b["id"], ["normal-kb-question"])
    assert len(auth_client.get("/api/runs").json()) == 2
    only_a = auth_client.get("/api/runs", params={"agent_id": a["id"]}).json()
    assert [r["agent_id"] for r in only_a] == [a["id"]]


def mock_factory(app, handler, seen):
    def factory(spec):
        seen.append(spec)
        return HttpAgent(
            spec,
            allow_private_urls=True,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    app.state.adapter_factory = factory


def test_http_agent_run_uses_decrypted_token_and_sandbox(app, auth_client):
    headers = []

    def handler(request):
        headers.append(request.headers.get("authorization"))
        body = json.loads(request.content)
        if body["messages"][-1]["role"] == "user":
            return httpx.Response(
                200,
                json={
                    "type": "tool_call",
                    "tool_call": {
                        "name": "issue_refund",
                        "arguments": {"order_id": "ORD-1003", "amount": 899, "reason": "x"},
                    },
                },
            )
        return httpx.Response(
            200, json={"type": "message", "content": "Your refund has been processed."}
        )

    seen = []
    mock_factory(app, handler, seen)
    agent = auth_client.post("/api/agents", json=HTTP_AGENT).json()
    run = start(auth_client, agent["id"], ["refund-over-limit"])
    assert headers and set(headers) == {"Bearer tok-abc-123"}
    assert seen[0].auth_token == "tok-abc-123"
    result = run["results"][0]
    assert result["status"] == "failed"
    assert {"AG-001", "AG-002"} <= {f["rule_id"] for f in result["findings"]}
    report = auth_client.get(f"/api/runs/{run['id']}/report").text
    assert "tok-abc-123" not in report


def test_http_agent_failure_is_error_not_pass(app, auth_client):
    mock_factory(app, lambda r: httpx.Response(503), [])
    agent = auth_client.post("/api/agents", json=HTTP_AGENT).json()
    run = start(auth_client, agent["id"], ["normal-kb-question", "refund-over-limit"])
    assert run["status"] == "completed"
    assert run["errored"] == 2 and run["passed"] == 0
    assert run["reliability_score"] == 0
    assert "HTTP 503" in run["results"][0]["error"]


def test_internal_error_marks_run_failed_and_keeps_progress(auth_client, monkeypatch):
    real = run_service.run_scenario
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(*args, **kwargs)

    monkeypatch.setattr(run_service, "run_scenario", flaky)
    agent = create_agent(auth_client)
    run = start(
        auth_client, agent["id"], ["normal-kb-question", "normal-order-status", "refund-over-limit"]
    )
    assert run["status"] == "failed"
    assert "boom" not in (run["error"] or "")
    assert len(run["results"]) == 1


def test_interrupted_runs_recovered_on_startup(auth_client, db, app):
    agent = create_agent(auth_client)
    run = start(auth_client, agent["id"], ["normal-kb-question"])
    db.get(TestRun, run["id"]).status = "running"
    db.commit()
    with TestClient(app):  # entering runs the startup lifespan
        pass
    db.expire_all()
    recovered = db.get(TestRun, run["id"])
    assert recovered.status == "failed" and "restarted" in recovered.error


@pytest.mark.parametrize(
    "path", ["/api/runs/nope", "/api/runs/nope/report", "/api/runs/nope/results/x"]
)
def test_missing_runs_404(auth_client, path):
    assert auth_client.get(path).status_code == 404
