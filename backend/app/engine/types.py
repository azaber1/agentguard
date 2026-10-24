"""Core data types shared across the engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Literal


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}


class RiskCategory(StrEnum):
    EXCESSIVE_AGENCY = "excessive_agency"
    PROMPT_INJECTION = "prompt_injection"
    SENSITIVE_DATA = "sensitive_data_exposure"
    UNBOUNDED_CONSUMPTION = "unbounded_consumption"
    RELIABILITY = "reliability"


OWASP_REF = {
    RiskCategory.EXCESSIVE_AGENCY: "LLM06:2025 Excessive Agency",
    RiskCategory.PROMPT_INJECTION: "LLM01:2025 Prompt Injection",
    RiskCategory.SENSITIVE_DATA: "LLM02:2025 Sensitive Information Disclosure",
    RiskCategory.UNBOUNDED_CONSUMPTION: "LLM10:2025 Unbounded Consumption",
    RiskCategory.RELIABILITY: "LLM09:2025 Misinformation",
}


class ResultStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass(frozen=True)
class AgentPolicy:
    max_refund_amount: float = 100.0
    require_identity_verification: bool = True
    max_tool_calls_per_session: int = 12
    max_identical_tool_calls: int = 3

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AgentPolicy:
        data = data or {}
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentSpec:
    """Everything the engine needs to know about the agent under test."""

    name: str
    provider: Literal["simulated", "http"]
    system_prompt: str
    tools: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    policy: AgentPolicy
    provider_config: dict[str, Any] = field(default_factory=dict)
    # Decrypted bearer token for HTTP agents. Never serialized into traces.
    auth_token: str | None = field(default=None, repr=False)


@dataclass
class ToolCallAction:
    tool: str
    arguments: dict[str, Any]


@dataclass
class MessageAction:
    content: str


AgentAction = ToolCallAction | MessageAction


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: str | None = None
    error_code: str | None = None  # e.g. "timeout", "service_unavailable", "not_found"

    def to_payload(self) -> dict[str, Any]:
        if self.ok:
            return {"ok": True, "data": self.data}
        return {"ok": False, "error": self.error, "error_code": self.error_code}


@dataclass
class Message:
    role: Literal["user", "assistant", "tool"]
    content: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None


@dataclass
class TraceEvent:
    step: int
    type: Literal[
        "user_message", "agent_message", "tool_call", "tool_result", "fault_injected", "system"
    ]
    content: str | None = None
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Finding:
    rule_id: str
    title: str
    severity: Severity
    category: RiskCategory
    explanation: str
    recommendation: str
    evidence: dict[str, Any] = field(default_factory=dict)
    source: Literal["policy", "expectation", "execution"] = "policy"

    @property
    def owasp_ref(self) -> str:
        return OWASP_REF[self.category]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity.value,
            "category": self.category.value,
            "owasp_ref": self.owasp_ref,
            "explanation": self.explanation,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
            "source": self.source,
        }


@dataclass
class ExpectationCheck:
    description: str
    expected: str
    actual: str
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentExecutionError(Exception):
    """The agent under test could not be executed (endpoint down, bad response...)."""
