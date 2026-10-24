"""Agent adapter interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.engine.types import AgentAction, AgentPolicy, Message


@dataclass
class AgentContext:
    session_id: str
    system_prompt: str
    tools: list[dict[str, Any]]
    policy: AgentPolicy
    messages: list[Message] = field(default_factory=list)


class AgentAdapter(Protocol):
    def next_action(self, ctx: AgentContext) -> AgentAction:
        """Return the agent's next action given the conversation so far.

        The last message is either a new user message or the result of the
        tool call the agent requested on the previous step.
        """
        ...

    def close(self) -> None: ...
