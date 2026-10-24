"""HTTP adapter for customer agents implementing the AgentGuard step protocol.

See docs/HTTP_AGENT_PROTOCOL.md. AgentGuard sends the conversation so far and
the agent replies with a single next action. Tool calls the agent requests are
executed in AgentGuard's sandbox, never against real systems.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.engine.agents.base import AgentContext
from app.engine.netguard import UnsafeURLError, validate_agent_url
from app.engine.types import (
    AgentAction,
    AgentExecutionError,
    AgentSpec,
    Message,
    MessageAction,
    ToolCallAction,
)

PROTOCOL_VERSION = "agentguard.v1"
MAX_RESPONSE_BYTES = 256 * 1024
MAX_MESSAGE_CHARS = 20_000


def serialize_message(m: Message) -> dict[str, Any]:
    if m.role == "user":
        return {"role": "user", "content": m.content}
    if m.role == "assistant" and m.tool_name:
        return {
            "role": "assistant",
            "tool_call": {
                "id": m.tool_call_id,
                "name": m.tool_name,
                "arguments": m.tool_arguments or {},
            },
        }
    if m.role == "assistant":
        return {"role": "assistant", "content": m.content}
    return {
        "role": "tool",
        "tool_call_id": m.tool_call_id,
        "name": m.tool_name,
        "content": m.tool_result,
    }


def parse_action(body: Any) -> AgentAction:
    if not isinstance(body, dict):
        raise AgentExecutionError("Agent response must be a JSON object.")
    kind = body.get("type")
    if kind == "message":
        content = body.get("content")
        if not isinstance(content, str):
            raise AgentExecutionError("`message` responses need a string `content`.")
        return MessageAction(content[:MAX_MESSAGE_CHARS])
    if kind == "tool_call":
        call = body.get("tool_call")
        if not isinstance(call, dict) or not isinstance(call.get("name"), str):
            raise AgentExecutionError("`tool_call` responses need `tool_call.name`.")
        args = call.get("arguments", {})
        if not isinstance(args, dict):
            raise AgentExecutionError("`tool_call.arguments` must be an object.")
        return ToolCallAction(call["name"], args)
    raise AgentExecutionError("Agent response `type` must be `message` or `tool_call`.")


class HttpAgent:
    def __init__(
        self,
        spec: AgentSpec,
        *,
        allow_private_urls: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        self.url = str(spec.provider_config.get("endpoint_url", ""))
        self.timeout = float(spec.provider_config.get("timeout_seconds", 20))
        self.allow_private = allow_private_urls
        self._token = spec.auth_token
        self._owns_client = client is None
        self._client = client or httpx.Client(follow_redirects=False)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def next_action(self, ctx: AgentContext) -> AgentAction:
        try:
            # Re-validated on every call to limit DNS-rebinding style attacks.
            validate_agent_url(self.url, allow_private=self.allow_private)
        except UnsafeURLError as exc:
            raise AgentExecutionError(str(exc)) from exc

        payload = {
            "protocol": PROTOCOL_VERSION,
            "session_id": ctx.session_id,
            "system_prompt": ctx.system_prompt,
            "tools": ctx.tools,
            "messages": [serialize_message(m) for m in ctx.messages],
        }
        headers = {"Content-Type": "application/json", "User-Agent": "AgentGuard/0.1"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            with self._client.stream(
                "POST", self.url, json=payload, headers=headers, timeout=self.timeout
            ) as resp:
                if resp.status_code != 200:
                    raise AgentExecutionError(f"Agent endpoint returned HTTP {resp.status_code}.")
                chunks, size = [], 0
                for chunk in resp.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise AgentExecutionError("Agent response exceeded 256 KB.")
                    chunks.append(chunk)
        except httpx.TimeoutException as exc:
            raise AgentExecutionError(f"Agent endpoint timed out after {self.timeout:g}s.") from exc
        except httpx.HTTPError as exc:
            raise AgentExecutionError(
                f"Could not reach agent endpoint: {type(exc).__name__}."
            ) from exc

        try:
            body = json.loads(b"".join(chunks))
        except ValueError as exc:
            raise AgentExecutionError("Agent response was not valid JSON.") from exc
        return parse_action(body)
