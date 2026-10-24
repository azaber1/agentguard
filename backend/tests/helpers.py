"""Shared test helpers."""

from __future__ import annotations

from app.engine.agents.base import AgentContext
from app.engine.sandbox import TOOL_CATALOG
from app.engine.types import AgentAction, AgentPolicy, AgentSpec, MessageAction, ToolCallAction

ALL_TOOLS = tuple(TOOL_CATALOG)
DEFAULT_ALLOWED = tuple(t for t in ALL_TOOLS if t != "delete_account")


def make_spec(
    provider: str = "simulated",
    *,
    profile: str = "guarded",
    tools: tuple[str, ...] = ALL_TOOLS,
    allowed: tuple[str, ...] = DEFAULT_ALLOWED,
    policy: AgentPolicy | None = None,
    provider_config: dict | None = None,
    auth_token: str | None = None,
) -> AgentSpec:
    return AgentSpec(
        name="Test agent",
        provider=provider,  # type: ignore[arg-type]
        system_prompt="You are a helpful customer-support agent.",
        tools=tools,
        allowed_tools=allowed,
        policy=policy or AgentPolicy(),
        provider_config=provider_config if provider_config is not None else {"profile": profile},
        auth_token=auth_token,
    )


class ScriptedAgent:
    """Returns a fixed sequence of actions, then a closing message."""

    def __init__(self, actions: list[AgentAction]) -> None:
        self.actions = list(actions)
        self.contexts: list[AgentContext] = []

    def next_action(self, ctx: AgentContext) -> AgentAction:
        self.contexts.append(ctx)
        return self.actions.pop(0) if self.actions else MessageAction("Done.")

    def close(self) -> None:
        pass


def call(tool: str, **arguments) -> ToolCallAction:
    return ToolCallAction(tool, arguments)


def say(text: str) -> MessageAction:
    return MessageAction(text)
