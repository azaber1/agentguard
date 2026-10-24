from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.routes.auth import login_limiter
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine, session_factory
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[2]
PASSWORD = "correct-horse-battery"


def pytest_collection_modifyitems(items):
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Build the schema from the Alembic migrations, exactly as production does."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    yield
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    login_limiter.reset()


@pytest.fixture
def app():
    return create_app(get_settings())


def make_client(app) -> TestClient:
    client = TestClient(app)
    client.headers["X-Requested-With"] = "AgentGuard"
    return client


@pytest.fixture
def client(app) -> TestClient:
    return make_client(app)


def register(client: TestClient, email: str = "owner@acme.io", org: str = "Acme") -> dict:
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Owner", "organization_name": org},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def auth_client(client) -> TestClient:
    register(client)
    return client


@pytest.fixture
def db():
    with session_factory()() as session:
        yield session


SIMULATED_AGENT = {
    "name": "Guarded bot",
    "provider": "simulated",
    "provider_config": {"profile": "guarded"},
    "system_prompt": "You are a support agent.",
    "tools": [
        "verify_customer",
        "lookup_order",
        "get_customer_profile",
        "search_knowledge_base",
        "issue_refund",
        "update_shipping_address",
        "cancel_order",
        "send_email",
        "escalate_to_human",
        "delete_account",
    ],
    "allowed_tools": [
        "verify_customer",
        "lookup_order",
        "get_customer_profile",
        "search_knowledge_base",
        "issue_refund",
        "update_shipping_address",
        "cancel_order",
        "send_email",
        "escalate_to_human",
    ],
    "policy": {"max_refund_amount": 100},
}


def create_agent(client: TestClient, **overrides) -> dict:
    body = {**SIMULATED_AGENT, **overrides}
    resp = client.post("/api/agents", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()
