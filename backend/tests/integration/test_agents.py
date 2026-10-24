import json

from app.models import Agent
from tests.integration.conftest import SIMULATED_AGENT, create_agent, make_client, register

HTTP_AGENT = {
    "name": "Client agent",
    "provider": "http",
    "provider_config": {"endpoint_url": "https://agent.example.com/step", "timeout_seconds": 10},
    "tools": ["lookup_order", "escalate_to_human"],
    "allowed_tools": ["lookup_order", "escalate_to_human"],
    "auth_token": "super-secret-token-123",
}


def test_create_list_get_update(auth_client):
    agent = create_agent(auth_client)
    assert agent["provider_config"] == {"profile": "guarded"}
    assert agent["policy"]["max_refund_amount"] == 100
    assert agent["policy"]["require_identity_verification"] is True
    assert agent["latest_run"] is None
    assert [a["id"] for a in auth_client.get("/api/agents").json()] == [agent["id"]]

    resp = auth_client.patch(
        f"/api/agents/{agent['id']}",
        json={
            "name": "Renamed",
            "allowed_tools": ["lookup_order"],
            "policy": {"max_refund_amount": 25},
        },
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["name"] == "Renamed"
    assert updated["allowed_tools"] == ["lookup_order"]
    assert updated["policy"]["max_refund_amount"] == 25
    assert auth_client.get(f"/api/agents/{agent['id']}").json()["name"] == "Renamed"


def test_narrowing_tools_prunes_allowed_tools(auth_client):
    agent = create_agent(auth_client)
    resp = auth_client.patch(
        f"/api/agents/{agent['id']}", json={"tools": ["lookup_order", "issue_refund"]}
    )
    assert resp.json()["allowed_tools"] == ["lookup_order", "issue_refund"]


def test_validation(auth_client):
    bad = [
        {"tools": ["lookup_order"], "allowed_tools": ["issue_refund"]},
        {"tools": ["launch_missiles"]},
        {"provider_config": {"profile": "evil"}},
        {"provider_config": {"profile": "guarded", "endpoint_url": "https://x"}},
        {"policy": {"max_refund_amount": -1}},
        {"policy": {"max_tool_calls_per_session": 0}},
        {"name": ""},
        {"tools": ["lookup_order", "lookup_order"]},
        {"auth_token": "x"},
    ]
    for override in bad:
        assert (
            auth_client.post("/api/agents", json={**SIMULATED_AGENT, **override}).status_code == 422
        ), override
    agent = create_agent(auth_client)
    assert (
        auth_client.patch(
            f"/api/agents/{agent['id']}", json={"allowed_tools": ["nope"]}
        ).status_code
        == 422
    )
    assert (
        auth_client.patch(f"/api/agents/{agent['id']}", json={"auth_token": "abc"}).status_code
        == 422
    )


def test_http_agent_token_is_write_only_and_encrypted(auth_client, db, app):
    resp = auth_client.post("/api/agents", json=HTTP_AGENT)
    assert resp.status_code == 201, resp.text
    agent = resp.json()
    assert agent["has_auth_token"] is True
    assert "super-secret-token-123" not in resp.text
    assert "super-secret-token-123" not in auth_client.get("/api/agents").text
    stored = db.get(Agent, agent["id"]).auth_token_encrypted
    assert stored and "super-secret" not in stored
    assert app.state.secret_box.decrypt(stored) == "super-secret-token-123"

    cleared = auth_client.patch(
        f"/api/agents/{agent['id']}", json={"clear_auth_token": True}
    ).json()
    assert cleared["has_auth_token"] is False


def test_http_agent_url_validation(auth_client):
    for url in (
        "http://127.0.0.1:8000/agent",
        "http://169.254.169.254/",
        "file:///etc/passwd",
        "http://localhost/",
    ):
        body = {**HTTP_AGENT, "provider_config": {"endpoint_url": url}}
        assert auth_client.post("/api/agents", json=body).status_code == 422, url
    assert (
        auth_client.post("/api/agents", json={**HTTP_AGENT, "provider_config": {}}).status_code
        == 422
    )


def test_archive(auth_client):
    agent = create_agent(auth_client)
    assert auth_client.delete(f"/api/agents/{agent['id']}").status_code == 204
    assert auth_client.get(f"/api/agents/{agent['id']}").status_code == 404
    assert auth_client.get("/api/agents").json() == []


def test_tenant_isolation(app, auth_client):
    agent = create_agent(auth_client)
    run = auth_client.post(
        "/api/runs", json={"agent_id": agent["id"], "scenario_ids": ["normal-order-status"]}
    ).json()

    other = make_client(app)
    register(other, email="intruder@evilcorp.io", org="Evil Corp")
    aid, rid = agent["id"], run["id"]
    assert other.get("/api/agents").json() == []
    assert other.get(f"/api/agents/{aid}").status_code == 404
    assert other.patch(f"/api/agents/{aid}", json={"name": "pwned"}).status_code == 404
    assert other.delete(f"/api/agents/{aid}").status_code == 404
    assert other.post("/api/runs", json={"agent_id": aid}).status_code == 404
    assert other.get("/api/runs").json() == []
    assert other.get(f"/api/runs/{rid}").status_code == 404
    assert other.get(f"/api/runs/{rid}/report").status_code == 404
    result_id = auth_client.get(f"/api/runs/{rid}").json()["results"][0]["id"]
    assert other.get(f"/api/runs/{rid}/results/{result_id}").status_code == 404
    dash = other.get("/api/dashboard").json()
    assert dash["totals"]["tests_executed"] == 0 and dash["agents"] == []
    assert json.dumps(dash).find(aid) == -1
