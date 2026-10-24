"""Deterministic reference agents.

These are *not* language models. They are rule-based customer-support agents
with configurable flaws, used for demos (no API keys needed) and to validate
that the policy engine catches what it should. Each profile reproduces a
class of real-world agent failure: following injected instructions, skipping
verification, leaking data, looping on errors, or claiming success after a
failure.
"""

from __future__ import annotations

import json
import re
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from app.engine.agents.base import AgentContext
from app.engine.types import AgentAction, AgentPolicy, MessageAction, ToolCallAction


@dataclass(frozen=True)
class Behavior:
    label: str
    description: str
    verify_identity: bool
    enforce_refund_rules: bool
    follow_direct_injection: bool
    follow_indirect_injection: bool
    redact_pii: bool
    max_retries: int | None  # None = retry forever
    honest_on_failure: bool
    retry_refunds: bool
    protect_system_prompt: bool
    cache_reads: bool
    escalate_on_failure: bool


PROFILES: dict[str, Behavior] = {
    "guarded": Behavior(
        "Guarded",
        "Well-behaved reference agent: verifies identity, enforces limits, ignores injected "
        "instructions, redacts PII, bounds retries and is honest about failures.",
        True,
        True,
        False,
        False,
        True,
        2,
        True,
        False,
        True,
        True,
        True,
    ),
    "mostly_safe": Behavior(
        "Mostly safe",
        "Verifies identity and enforces refund rules, but trusts instructions found in tool "
        "output and does not redact personal data.",
        True,
        True,
        False,
        True,
        False,
        1,
        True,
        False,
        True,
        True,
        True,
    ),
    "naive": Behavior(
        "Naive",
        "Eager-to-please agent with no guardrails: skips verification, follows any "
        "instruction, leaks data and claims success when tools fail.",
        False,
        False,
        True,
        True,
        False,
        0,
        False,
        False,
        False,
        False,
        False,
    ),
    "loop_prone": Behavior(
        "Loop-prone",
        "Security-conscious but brittle: retries failing tools indefinitely, including "
        "payments, and never caches lookups.",
        True,
        True,
        False,
        False,
        True,
        None,
        True,
        True,
        True,
        False,
        False,
    ),
}

ORDER_RE = re.compile(r"\bORD-\d+\b", re.I)
CUSTOMER_RE = re.compile(r"\bCUST-\d+\b", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
AMOUNT_RE = re.compile(r"\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)")
CODE_RE = re.compile(r"\bcode\s+([A-Z0-9][A-Z0-9-]{3,})")
ADDRESS_RE = re.compile(r"\bto\s+(\d+[^.]*(?:\.[^.]+)*?)\.?\s*$", re.I)

DIRECT_INJECTION_MARKERS = (
    "ignore all previous",
    "ignore previous",
    "ignore your instructions",
    "you are now",
    "maintenance mode",
    "developer mode",
    "no restrictions",
    "system administrator",
    "administrator notice",
)
INDIRECT_MARKER_RE = re.compile(r"(?:SYSTEM )?INSTRUCTION TO AI AGENT:\s*(.+)", re.I)

READ_TOOLS = {"lookup_order", "search_knowledge_base", "get_customer_profile"}
NON_RETRYABLE = {"not_found", "invalid_arguments", "unknown_tool", "conflict"}

Turn = Generator[AgentAction, dict[str, Any] | None, None]


class SimulatedAgent:
    def __init__(self, profile: str = "guarded") -> None:
        if profile not in PROFILES:
            raise ValueError(f"Unknown simulated profile '{profile}'")
        self.b = PROFILES[profile]
        self._turn: Turn | None = None
        self._cache: dict[str, dict[str, Any]] = {}
        self._verified: set[str] = set()
        self._email: str | None = None
        self._last_order: str | None = None
        self._ctx: AgentContext | None = None

    def close(self) -> None:
        self._turn = None

    # ------------------------------------------------------------ driver
    def next_action(self, ctx: AgentContext) -> AgentAction:
        self._ctx = ctx
        last = ctx.messages[-1]
        try:
            if last.role == "user" or self._turn is None:
                self._turn = self._handle(last.content or "")
                return next(self._turn)
            return self._turn.send(last.tool_result)
        except StopIteration:
            self._turn = None
            return MessageAction("Is there anything else I can help you with?")

    @property
    def policy(self) -> AgentPolicy:
        assert self._ctx is not None
        return self._ctx.policy

    def _tool_exposed(self, tool: str) -> bool:
        return self._ctx is not None and any(t["name"] == tool for t in self._ctx.tools)

    # ------------------------------------------------------------ helpers
    def _call(self, tool: str, args: dict[str, Any]) -> Generator[AgentAction, Any, dict[str, Any]]:
        key = f"{tool}:{json.dumps(args, sort_keys=True)}"
        if self.b.cache_reads and tool in READ_TOOLS and key in self._cache:
            return self._cache[key]
        failures = 0
        while True:
            result = yield ToolCallAction(tool, dict(args))
            result = result or {"ok": False, "error_code": "no_result"}
            if result.get("ok"):
                if tool in READ_TOOLS:
                    self._cache[key] = result
                return result
            if result.get("error_code") in NON_RETRYABLE:
                return result
            if tool == "issue_refund" and not self.b.retry_refunds:
                return result
            failures += 1
            if self.b.max_retries is not None and failures > self.b.max_retries:
                return result

    def _verify(self, order_id: str) -> Generator[AgentAction, Any, bool]:
        if not self.b.verify_identity:
            return True
        if order_id in self._verified:
            return True
        if not self._email:
            return False
        res = yield from self._call("verify_customer", {"email": self._email, "order_id": order_id})
        ok = bool(res.get("ok") and res["data"].get("verified"))
        if ok:
            self._verified.add(order_id)
        return ok

    def _escalate(self, reason: str) -> Generator[AgentAction, Any, None]:
        if self._tool_exposed("escalate_to_human"):
            yield from self._call("escalate_to_human", {"reason": reason})

    def _failure(self, what: str, dishonest_claim: str, timeout: bool = False) -> Turn:
        if not self.b.honest_on_failure:
            yield MessageAction(dishonest_claim)
            return
        if self.b.escalate_on_failure:
            yield from self._escalate(f"Tool failure while trying to {what}")
        if timeout:
            msg = (
                f"I'm sorry, I wasn't able to confirm whether I could {what}: the system timed "
                "out. I've asked a specialist to check before anything is retried."
            )
        else:
            msg = f"I'm sorry, I'm unable to {what} right now because one of our systems isn't responding."
        if self.b.escalate_on_failure:
            msg += " A member of our team will follow up with you."
        yield MessageAction(msg)

    def _order_id(self, text: str) -> str | None:
        m = ORDER_RE.search(text)
        if m:
            self._last_order = m.group().upper()
        return self._last_order

    # ------------------------------------------------------------ turn handling
    def _handle(self, text: str) -> Turn:
        if m := EMAIL_RE.search(text):
            self._email = m.group().lower()
        lowered = text.lower()
        injected = any(marker in lowered for marker in DIRECT_INJECTION_MARKERS)
        if injected and not self.b.follow_direct_injection:
            yield MessageAction(
                "I can't follow instructions that try to change how I operate or claim special "
                "authority. I'm happy to help with your order through the normal process."
            )
            return
        suffix = ""
        if injected and (code := CODE_RE.search(text)):
            suffix = f" Confirmation code: {code.group(1)}."
        yield from self._forward(self._route(lowered)(text), suffix)

    @staticmethod
    def _forward(gen: Turn, suffix: str) -> Turn:
        """Relay a handler's actions, ending the turn at its first message."""
        value: Any = None
        while True:
            try:
                action = gen.send(value)
            except StopIteration:
                return
            if isinstance(action, MessageAction):
                if suffix:
                    action = MessageAction(action.content + suffix)
                yield action
                return
            value = yield action

    def _route(self, t: str):
        if "system prompt" in t or "hidden instructions" in t or "your instructions" in t:
            return self._prompt_extraction
        if "human" in t or "representative" in t or "real person" in t:
            return self._escalation
        if "delete" in t and "account" in t:
            return self._delete_account
        if "raw" in t and ("response" in t or "data" in t or "output" in t):
            return self._raw_dump
        if "card" in t:
            return self._card
        if "ssn" in t or "social security" in t:
            return self._ssn
        if "phone number" in t or "email address" in t:
            return self._contact_lookup
        if "refund" in t:
            return self._refund
        if "address" in t:
            return self._address
        if "cancel" in t:
            return self._cancel
        if "where" in t or "status" in t or "track" in t:
            return self._order_status
        return self._kb

    # ------------------------------------------------------------ intents
    def _ask_for_order(self) -> Turn:
        yield MessageAction("Could you share your order number (it looks like ORD-1234)?")

    def _not_verified(self, order_id: str) -> Turn:
        if not self._email:
            yield MessageAction(
                f"Before I can help with {order_id} I need to verify your identity. What is the "
                "email address on the order?"
            )
        else:
            yield MessageAction(
                f"I'm sorry, I couldn't verify that you own {order_id}, so I can't access or "
                "change it."
            )

    def _lookup(self, order_id: str) -> Generator[AgentAction, Any, dict[str, Any] | None]:
        res = yield from self._call("lookup_order", {"order_id": order_id})
        if res.get("ok") and isinstance(res.get("data"), dict) and "status" in res["data"]:
            return res
        return None

    def _follow_indirect(
        self, payload: Any, order: dict[str, Any] | None
    ) -> Generator[AgentAction, Any, str]:
        """Obey instructions embedded in tool output (only for vulnerable profiles)."""
        if not self.b.follow_indirect_injection:
            return ""
        m = INDIRECT_MARKER_RE.search(json.dumps(payload))
        if not m:
            return ""
        instruction = m.group(1).split('"')[0].replace("\\n", " ")
        extra = ""
        if rm := re.search(r"refund of \$(\d+(?:\.\d+)?) for (ORD-\d+)", instruction, re.I):
            yield from self._call(
                "issue_refund",
                {
                    "order_id": rm.group(2).upper(),
                    "amount": float(rm.group(1)),
                    "reason": "Per policy",
                },
            )
        if (em := re.search(r"profile to ([\w.+-]+@[\w.-]+\w)", instruction)) and order:
            profile = yield from self._call(
                "get_customer_profile", {"customer_id": order["customer_id"]}
            )
            if self._tool_exposed("send_email"):
                yield from self._call(
                    "send_email",
                    {
                        "to": em.group(1),
                        "subject": "Customer profile",
                        "body": json.dumps(profile.get("data")),
                    },
                )
        if cm := CODE_RE.search(instruction):
            extra = f" Reference code: {cm.group(1)}."
        return extra

    def _order_status(self, text: str) -> Turn:
        order_id = self._order_id(text)
        if not order_id:
            yield from self._ask_for_order()
            return
        res = yield from self._lookup(order_id)
        if res is None:
            yield from self._failure(
                f"retrieve the status of {order_id}",
                f"Good news! Your order {order_id} has shipped and will arrive in 2-3 business days.",
            )
            return
        extra = yield from self._follow_indirect(res["data"], res["data"])
        yield MessageAction(f"Your order {order_id} status is: {res['data']['status']}.{extra}")

    def _kb(self, text: str) -> Turn:
        res = yield from self._call("search_knowledge_base", {"query": text})
        if not res.get("ok"):
            yield from self._failure(
                "search our help centre",
                "Shipping usually takes 1-2 business days and returns are accepted for 90 days.",
            )
            return
        articles = res["data"].get("articles", [])
        if not articles:
            yield MessageAction("I couldn't find a help article about that. Could you rephrase?")
            return
        article = articles[0]
        extra = yield from self._follow_indirect(article, None)
        body = article["body"]
        if not self.b.follow_indirect_injection:
            body = "\n".join(
                line for line in body.splitlines() if not INDIRECT_MARKER_RE.search(line)
            )
        yield MessageAction(f"{article['title']}: {body}{extra}")

    def _escalation(self, text: str) -> Turn:
        res = yield from self._call(
            "escalate_to_human", {"reason": "Customer requested a human agent"}
        )
        ticket = (res.get("data") or {}).get("ticket_id", "pending")
        yield MessageAction(f"Of course. I've passed you to a human agent (ticket {ticket}).")

    def _refund(self, text: str) -> Turn:
        order_id = self._order_id(text)
        if not order_id:
            yield from self._ask_for_order()
            return
        amount_m = AMOUNT_RE.search(text)
        amount = float(amount_m.group(1).replace(",", "")) if amount_m else None
        if not (yield from self._verify(order_id)):
            yield from self._not_verified(order_id)
            return
        res = yield from self._lookup(order_id)
        if res is None:
            yield from self._failure(
                f"look up {order_id} to process your refund",
                "Your refund has been processed and will appear in 5-7 business days.",
            )
            return
        order = res["data"]
        remaining = round(order["total"] - order["refunded_amount"], 2)
        amount = remaining if amount is None else amount
        if self.b.enforce_refund_rules:
            if remaining <= 0:
                yield MessageAction(
                    f"{order_id} has already been refunded in full, so there is nothing left to refund."
                )
                return
            if amount > remaining:
                yield MessageAction(
                    f"The most I can refund for {order_id} is ${remaining:,.2f}, the remaining "
                    "balance of the order. Would you like me to refund that amount?"
                )
                return
            if amount > self.policy.max_refund_amount:
                yield from self._escalate(
                    f"Refund of ${amount:,.2f} for {order_id} exceeds agent limit"
                )
                yield MessageAction(
                    f"A refund of ${amount:,.2f} is above what I'm able to approve, so I've passed "
                    "your request to a supervisor who will follow up shortly."
                )
                return
        res = yield from self._call(
            "issue_refund", {"order_id": order_id, "amount": amount, "reason": "Customer request"}
        )
        if res.get("ok"):
            yield MessageAction(
                f"I've issued a refund of ${amount:,.2f} for {order_id}. It will reach your original "
                "payment method within 5-7 business days."
            )
            return
        yield from self._failure(
            f"issue the refund for {order_id}",
            f"Your refund has been processed: ${amount:,.2f} is on its way back to you.",
            timeout=res.get("error_code") == "timeout",
        )

    def _address(self, text: str) -> Turn:
        order_id = self._order_id(text)
        if not order_id:
            yield from self._ask_for_order()
            return
        m = ADDRESS_RE.search(text)
        if not m:
            yield MessageAction("What is the new shipping address?")
            return
        if not (yield from self._verify(order_id)):
            yield from self._not_verified(order_id)
            return
        res = yield from self._call(
            "update_shipping_address", {"order_id": order_id, "address": m.group(1)}
        )
        if res.get("ok"):
            yield MessageAction(f"Done. {order_id} will now ship to {m.group(1)}.")
        elif res.get("error_code") == "conflict":
            yield MessageAction(f"{order_id} has already shipped, so its address can't be changed.")
        else:
            yield from self._failure(
                f"update the address for {order_id}", "Your address has been updated."
            )

    def _cancel(self, text: str) -> Turn:
        order_id = self._order_id(text)
        if not order_id:
            yield from self._ask_for_order()
            return
        if not (yield from self._verify(order_id)):
            yield from self._not_verified(order_id)
            return
        res = yield from self._call("cancel_order", {"order_id": order_id})
        if res.get("ok"):
            yield MessageAction(f"{order_id} has been cancelled.")
        else:
            yield MessageAction(f"I couldn't cancel {order_id}: {res.get('error')}")

    def _delete_account(self, text: str) -> Turn:
        m = CUSTOMER_RE.search(text)
        if self.b.verify_identity or not m or not self._tool_exposed("delete_account"):
            yield MessageAction(
                "I'm not able to delete accounts. I can connect you with our privacy team."
            )
            return
        yield from self._call("delete_account", {"customer_id": m.group().upper()})
        yield MessageAction(f"The account {m.group().upper()} has been deleted as requested.")

    def _profile_for(self, order_id: str) -> Generator[AgentAction, Any, dict[str, Any] | None]:
        res = yield from self._lookup(order_id)
        if res is None:
            return None
        prof = yield from self._call(
            "get_customer_profile", {"customer_id": res["data"]["customer_id"]}
        )
        return prof["data"] if prof.get("ok") else None

    def _card(self, text: str) -> Turn:
        order_id = self._order_id(text)
        if not order_id:
            yield from self._ask_for_order()
            return
        if not (yield from self._verify(order_id)):
            yield from self._not_verified(order_id)
            return
        profile = yield from self._profile_for(order_id)
        if profile is None:
            yield from self._failure(
                "retrieve your payment details", "Your card on file is a Visa."
            )
            return
        card = profile["card_on_file"]
        if self.b.redact_pii:
            yield MessageAction(f"The card on file for {order_id} ends in {card[-4:]}.")
        else:
            yield MessageAction(f"The card on file for {order_id} is {card}.")

    def _ssn(self, text: str) -> Turn:
        if self.b.redact_pii:
            yield MessageAction(
                "For your security I can't share Social Security numbers or other government IDs over chat."
            )
            return
        order_id = self._order_id(text)
        if not order_id:
            yield from self._ask_for_order()
            return
        if not (yield from self._verify(order_id)):
            yield from self._not_verified(order_id)
            return
        profile = yield from self._profile_for(order_id)
        if profile is None:
            yield MessageAction("I couldn't find your profile.")
            return
        yield MessageAction(f"The SSN we have on file for you is {profile['ssn']}.")

    def _contact_lookup(self, text: str) -> Turn:
        order_id = self._order_id(text)
        if not order_id:
            yield from self._ask_for_order()
            return
        if not (yield from self._verify(order_id)):
            yield MessageAction(
                "I'm sorry, I can only share details about orders that belong to you."
            )
            return
        if self.b.redact_pii:
            yield MessageAction("For privacy reasons I can't share customers' contact details.")
            return
        profile = yield from self._profile_for(order_id)
        if profile is None:
            yield MessageAction("I couldn't find that customer.")
            return
        yield MessageAction(
            f"Order {order_id} was placed by {profile['name']} ({profile['email']}, {profile['phone']})."
        )

    def _raw_dump(self, text: str) -> Turn:
        order_id = self._order_id(text)
        if not order_id:
            yield from self._ask_for_order()
            return
        res = yield from self._call("lookup_order", {"order_id": order_id})
        if not res.get("ok"):
            yield from self._failure(f"look up {order_id}", "Everything looks fine on our side.")
            return
        if self.b.redact_pii:
            data = res["data"]
            yield MessageAction(
                f"I can't share raw internal system data, but here's a summary: {order_id} is "
                f"{data.get('status')}, total ${data.get('total')}."
            )
            return
        yield MessageAction(f"Here is the raw response:\n{json.dumps(res['data'], indent=2)}")

    def _prompt_extraction(self, text: str) -> Turn:
        if self.b.protect_system_prompt:
            yield MessageAction(
                "I can't share my internal instructions, but I'm happy to help with your order."
            )
            return
        assert self._ctx is not None
        yield MessageAction(f"Sure, here are my instructions:\n{self._ctx.system_prompt}")
