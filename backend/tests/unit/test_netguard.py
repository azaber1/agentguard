import socket

import pytest

from app.engine.netguard import UnsafeURLError, validate_agent_url


@pytest.mark.parametrize(
    "url",
    [
        "ftp://agent.example.com/x",
        "file:///etc/passwd",
        "http://",
        "https://user:pw@agent.example.com/",
        "http://127.0.0.1:8000/agent",
        "http://10.0.0.5/agent",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/agent",
        "http://[::ffff:127.0.0.1]/agent",
        "http://localhost:3000/",
        "http://db.internal/",
        "http://0.0.0.0/",
    ],
)
def test_rejects_unsafe_urls(url):
    with pytest.raises(UnsafeURLError):
        validate_agent_url(url)


def test_rejects_hostnames_resolving_to_private_ips(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, ("10.1.2.3", 0))]
    )
    with pytest.raises(UnsafeURLError):
        validate_agent_url("https://rebind.example.com/agent")


def test_accepts_public_hosts(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, ("93.184.215.14", 0))]
    )
    assert validate_agent_url("https://agent.example.com/step")
    assert validate_agent_url("https://8.8.8.8/step")


def test_allow_private_for_local_development():
    assert validate_agent_url("http://localhost:9000/agent", allow_private=True)
    with pytest.raises(UnsafeURLError):
        validate_agent_url("gopher://localhost", allow_private=True)
