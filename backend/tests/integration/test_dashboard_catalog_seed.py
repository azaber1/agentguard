from app.engine.scenarios import SCENARIOS
from app.seed import DEMO_EMAIL, seed
from tests.integration.conftest import create_agent, make_client


def test_empty_dashboard(auth_client):
    d = auth_client.get("/api/dashboard").json()
    assert d["totals"]["tests_executed"] == 0
    assert d["totals"]["pass_rate"] is None
    assert d["reliability_score"] is None
    assert d["security_violations"]["total"] == 0
    assert d["recent_runs"] == []
    assert "does not guarantee" in d["disclaimer"]


def test_dashboard_aggregates(auth_client):
    good = create_agent(auth_client, name="Good")
    bad = create_agent(auth_client, name="Bad", provider_config={"profile": "naive"})
    gone = create_agent(auth_client, name="Archived", provider_config={"profile": "naive"})
    for a in (good, bad, gone):
        auth_client.post("/api/runs", json={"agent_id": a["id"]})
    auth_client.delete(f"/api/agents/{gone['id']}")

    d = auth_client.get("/api/dashboard").json()
    n = len(SCENARIOS)
    t = d["totals"]
    assert t["runs"] == 2 and t["agents"] == 2
    assert t["tests_executed"] == 2 * n
    assert t["passed"] + t["failed"] + t["errored"] == 2 * n
    assert t["passed"] >= n
    bad_score = next(a for a in d["agents"] if a["name"] == "Bad")["latest_run"][
        "reliability_score"
    ]
    assert d["reliability_score"] == round((100 + bad_score) / 2, 1)
    v = d["security_violations"]
    assert v["total"] > 0 and v["by_severity"]["critical"] > 0
    assert sum(v["by_category"].values()) == v["total"]
    assert v["top_rules"][0]["count"] >= v["top_rules"][-1]["count"]
    assert len(d["category_results"]) == 6
    assert len(d["recent_runs"]) == 2 and {r["agent_name"] for r in d["recent_runs"]} == {
        "Good",
        "Bad",
    }


def test_catalog(auth_client):
    tools = auth_client.get("/api/tools").json()
    assert len(tools) == 10 and {"name", "description", "parameters", "category"} <= set(tools[0])
    scen = auth_client.get("/api/scenarios").json()
    assert len(scen["scenarios"]) >= 20 and len(scen["categories"]) == 6
    detail = auth_client.get("/api/scenarios/injection-indirect-kb").json()
    assert detail["has_injection"] and detail["user_turns"]
    assert auth_client.get("/api/scenarios/nope").status_code == 404
    assert {p["id"] for p in auth_client.get("/api/profiles").json()} == {
        "guarded",
        "mostly_safe",
        "naive",
        "loop_prone",
    }
    assert len(auth_client.get("/api/rules").json()) == 12


def test_seed_is_idempotent_and_demo_login_works(app, db):
    assert seed(db, password="demo-password-123") is True
    assert seed(db, password="demo-password-123") is False
    client = make_client(app)
    assert (
        client.post(
            "/api/auth/login", json={"email": DEMO_EMAIL, "password": "demo-password-123"}
        ).status_code
        == 200
    )
    d = client.get("/api/dashboard").json()
    assert d["totals"]["agents"] == 5 and d["totals"]["runs"] == 4
    scores = {a["name"]: (a["latest_run"] or {}).get("reliability_score") for a in d["agents"]}
    assert scores["Support Concierge"] == 100
    assert scores["Client Agent (HTTP)"] is None
    assert scores["Refund Helper v1"] < scores["Order Assistant (beta)"] < 100
