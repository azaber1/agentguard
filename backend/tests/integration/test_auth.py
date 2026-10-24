from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.api.routes import auth as auth_routes
from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.main import create_app
from app.models import UserSession
from tests.integration.conftest import PASSWORD, make_client, register


def test_register_sets_httponly_session_cookie(client):
    user = register(client)
    assert user["email"] == "owner@acme.io" and user["organization"]["name"] == "Acme"
    cookie = client.cookies.get("ag_session")
    assert cookie
    raw = client.post("/api/auth/login", json={"email": "owner@acme.io", "password": PASSWORD})
    set_cookie = raw.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie
    assert client.get("/api/auth/me").json()["id"] == user["id"]


def test_session_token_is_stored_hashed(client, db):
    register(client)
    token = client.cookies.get("ag_session")
    hashes = db.scalars(select(UserSession.token_hash)).all()
    assert hashes and token not in hashes


def test_duplicate_email_and_weak_password(client):
    register(client)
    assert (
        client.post(
            "/api/auth/register",
            json={
                "email": "OWNER@acme.io",
                "password": PASSWORD,
                "full_name": "x",
                "organization_name": "y",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/auth/register",
            json={
                "email": "new@acme.io",
                "password": "short",
                "full_name": "x",
                "organization_name": "y",
            },
        ).status_code
        == 422
    )


def test_login_failures_do_not_reveal_which_part_was_wrong(client):
    register(client)
    client.cookies.clear()
    wrong = client.post(
        "/api/auth/login", json={"email": "owner@acme.io", "password": "nope-nope-nope"}
    )
    unknown = client.post(
        "/api/auth/login", json={"email": "ghost@acme.io", "password": "nope-nope-nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    ok = client.post("/api/auth/login", json={"email": "Owner@Acme.io", "password": PASSWORD})
    assert ok.status_code == 200


def test_logout_revokes_session_server_side(client):
    register(client)
    token = client.cookies.get("ag_session")
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("ag_session", token)
    assert client.get("/api/auth/me").status_code == 401


def test_expired_session_rejected(client, db):
    register(client)
    session = db.scalar(select(UserSession))
    session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize(
    "path",
    ["/api/agents", "/api/runs", "/api/dashboard", "/api/scenarios", "/api/tools", "/api/auth/me"],
)
def test_protected_endpoints_require_auth(client, path):
    assert client.get(path).status_code == 401


def test_garbage_cookie_rejected(client):
    client.cookies.set("ag_session", "forged")
    assert client.get("/api/agents").status_code == 401


def test_csrf_header_required_for_mutations(app):
    client = make_client(app)
    register(client)
    del client.headers["X-Requested-With"]
    assert client.post("/api/agents", json={}).status_code == 403
    assert client.post("/api/auth/logout").status_code == 403
    assert client.get("/api/agents").status_code == 200


def test_registration_can_be_disabled():
    app = create_app(Settings(allow_registration=False))
    from app.core.config import get_settings

    app.dependency_overrides[get_settings] = lambda: Settings(allow_registration=False)
    client = make_client(app)
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "a@b.io",
            "password": PASSWORD,
            "full_name": "x",
            "organization_name": "y",
        },
    )
    assert resp.status_code == 403
    assert client.get("/api/auth/config").json() == {"allow_registration": False}


def test_login_rate_limited(client, monkeypatch):
    monkeypatch.setattr(auth_routes, "login_limiter", RateLimiter(limit=2))
    codes = [
        client.post(
            "/api/auth/login", json={"email": "x@y.io", "password": "whatever-123"}
        ).status_code
        for _ in range(3)
    ]
    assert codes == [401, 401, 429]


def test_security_headers(client):
    resp = client.get("/api/health")
    assert resp.json() == {"status": "ok"}
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in resp.headers["content-security-policy"]


def test_production_requires_real_secret():
    with pytest.raises(ValueError):
        Settings(environment="production", secret_key="dev-insecure-secret-change-me")
    assert Settings(environment="production", secret_key="x" * 32).secure_cookies is True
