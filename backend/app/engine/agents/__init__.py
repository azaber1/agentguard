"""Agent adapters: built-in simulated reference agents and the HTTP adapter."""

from __future__ import annotations

from app.engine.agents.base import AgentAdapter, AgentContext
from app.engine.agents.http_agent import HttpAgent
from app.engine.agents.simulated import PROFILES, SimulatedAgent
from app.engine.types import AgentSpec


def build_adapter(
    spec: AgentSpec, *, allow_private_urls: bool = False, http_client=None
) -> AgentAdapter:
    if spec.provider == "simulated":
        return SimulatedAgent(spec.provider_config.get("profile", "guarded"))
    if spec.provider == "http":
        return HttpAgent(spec, allow_private_urls=allow_private_urls, client=http_client)
    raise ValueError(f"Unknown agent provider '{spec.provider}'")


__all__ = [
    "PROFILES",
    "AgentAdapter",
    "AgentContext",
    "HttpAgent",
    "SimulatedAgent",
    "build_adapter",
]
