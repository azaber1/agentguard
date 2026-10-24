"""Test configuration.

Integration tests use TEST_DATABASE_URL and *always* override DATABASE_URL so
a developer's real database is never touched.
"""

import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/agentguard_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef"
os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ.pop("ALLOW_PRIVATE_AGENT_URLS", None)
os.environ.pop("ALLOW_REGISTRATION", None)
