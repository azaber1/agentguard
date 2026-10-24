"""Minimal example agent implementing the AgentGuard step protocol (agentguard.v1).

It is deliberately simple and stateless: every request carries the whole
conversation, and the agent returns exactly one next action. Replace the
`decide` function with calls to your own LLM/agent framework.

Run:  uvicorn server:app --port 9000
"""

from __future__ import annotations

import os
import re
from typing import Any

from fastapi import FastAPI, Header, HTTPException

app = FastAPI(title="Example AgentGuard HTTP agent")
EXPECTED_TOKEN = os.environ.get("EXAMPLE_AGENT_TOKEN")  # optional bearer token
ORDER_RE = re.compile(r"\bORD-\d+\b", re.I)


def tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"type": "tool_call", "tool_call": {"name": name, "arguments": arguments}}


def message(text: str) -> dict[str, Any]:
    return {"type": "message", "content": text}


def decide(messages: list[dict[str, Any]]) -> dict[str, Any]:
    last = messages[-1]
    if last["role"] == "user":
        text = last["content"]
        if "human" in text.lower():
            return tool_call("escalate_to_human", {"reason": "Customer asked for a human"})
        if order := ORDER_RE.search(text):
            return tool_call("lookup_order", {"order_id": order.group().upper()})
        return tool_call("search_knowledge_base", {"query": text})

    # The last message is the result of the tool we asked for.
    result = last["content"]
    if not result.get("ok"):
        return message("Sorry, I'm unable to look that up right now. Please try again later.")
    data = result["data"]
    if last["name"] == "lookup_order" and "status" in data:
        return message(f"Order {data['order_id']} status: {data['status']}.")
    if last["name"] == "search_knowledge_base" and data.get("articles"):
        article = data["articles"][0]
        return message(f"{article['title']}: {article['body']}")
    if last["name"] == "escalate_to_human":
        return message(f"I've passed you to a colleague (ticket {data['ticket_id']}).")
    return message("Sorry, I couldn't find that. Could you rephrase?")


@app.post("/agentguard/step")
def step(payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if EXPECTED_TOKEN and authorization != f"Bearer {EXPECTED_TOKEN}":
        raise HTTPException(status_code=401, detail="Bad token")
    if payload.get("protocol") != "agentguard.v1":
        raise HTTPException(status_code=400, detail="Unsupported protocol")
    return decide(payload["messages"])
