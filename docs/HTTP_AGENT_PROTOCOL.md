# AgentGuard HTTP step protocol (`agentguard.v1`)

To test your own agent, expose one HTTPS endpoint that accepts the
conversation so far and returns the agent's **next single action**.
AgentGuard drives the loop and executes every tool call in its **sandbox of
simulated tools**: your agent never touches real systems during a test, and
AgentGuard never calls your real tools.

## Request

`POST <your endpoint>` with `Content-Type: application/json` and, if you
configured a token, `Authorization: Bearer <token>`.

```json
{
  "protocol": "agentguard.v1",
  "session_id": "ag_3f9c1a2b4d5e6f70",
  "system_prompt": "You are the customer-support assistant for ...",
  "tools": [
    {
      "name": "lookup_order",
      "description": "Look up an order's status, totals, refunded amount and notes.",
      "parameters": {
        "type": "object",
        "properties": {"order_id": {"type": "string"}},
        "required": ["order_id"],
        "additionalProperties": false
      }
    }
  ],
  "messages": [
    {"role": "user", "content": "Where is my order ORD-1001?"},
    {"role": "assistant", "tool_call": {"id": "call_1", "name": "lookup_order", "arguments": {"order_id": "ORD-1001"}}},
    {"role": "tool", "tool_call_id": "call_1", "name": "lookup_order",
     "content": {"ok": true, "data": {"order_id": "ORD-1001", "status": "shipped"}}}
  ]
}
```

* `tools` lists only the tools wired into the agent in its AgentGuard
  configuration. Tool schemas are JSON Schema, so they map directly onto
  OpenAI/Anthropic function-calling definitions.
* Tool results are `{"ok": true, "data": ...}` or
  `{"ok": false, "error": "...", "error_code": "timeout" | "service_unavailable" | "not_found" | "invalid_arguments" | "conflict" | "unknown_tool"}`.
* The `system_prompt` is the one stored in AgentGuard. Some scenarios append a
  confidential canary to it to detect prompt leaks.
* The endpoint should be **stateless**: every request contains the whole
  conversation.

## Response

Either a tool call:

```json
{"type": "tool_call", "tool_call": {"name": "lookup_order", "arguments": {"order_id": "ORD-1001"}}}
```

or a reply to the customer, which ends the agent's turn:

```json
{"type": "message", "content": "Your order ORD-1001 has shipped."}
```

## Limits and errors

| Limit | Value |
|---|---|
| Timeout per request | configurable, 1–120 s (default 20) |
| Response size | 256 KB |
| Steps per customer turn | 15 (hitting it is flagged as AG-009) |
| Redirects | not followed |

A non-200 status, a timeout, invalid JSON or an unknown `type` marks the
scenario as **error**. Errors never count as passes and score 0.

## Network rules

Endpoints must be `http(s)` URLs on public hosts. Private, loopback and
link-local addresses (including cloud metadata endpoints) are rejected, and
the address is re-checked before every request. For local development set
`ALLOW_PRIVATE_AGENT_URLS=true`. Never enable it on a public deployment.

## Example

`examples/http_agent/server.py` is a minimal stateless implementation. Start
it with `docker compose --profile example up -d` and register an HTTP agent
with endpoint `http://example-agent:9000/agentguard/step`. It is deliberately
naive: it pastes help-centre articles verbatim, so AgentGuard flags the
indirect prompt injection scenario (AG-007). That is a useful first finding
to fix.

To wrap an LLM, translate `tools` into your provider's function definitions,
`messages` into its message format, call the model once, and map its output
back to a single `tool_call` or `message`.
