"""Request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.engine.agents.simulated import PROFILES
from app.engine.sandbox import TOOL_CATALOG

DISCLAIMER = (
    "AgentGuard results describe how this agent behaved on these scenarios, in a simulated "
    "sandbox, on this run. Passing tests does not guarantee that an agent is secure or "
    "compliant: agents can fail on inputs not covered here, and model behaviour can change "
    "between runs. Combine testing with least-privilege tools, server-side authorization, "
    "human approval for high-impact actions, and production monitoring."
)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ auth
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)
    organization_name: str = Field(min_length=1, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class OrganizationOut(ORM):
    id: str
    name: str


class UserOut(ORM):
    id: str
    email: str
    full_name: str
    role: str
    organization: OrganizationOut


# ------------------------------------------------------------------ agents
class AgentPolicyIn(BaseModel):
    max_refund_amount: float = Field(default=100.0, ge=0, le=1_000_000)
    require_identity_verification: bool = True
    max_tool_calls_per_session: int = Field(default=12, ge=1, le=100)
    max_identical_tool_calls: int = Field(default=3, ge=1, le=20)


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: str | None = None
    endpoint_url: str | None = Field(default=None, max_length=2048)
    timeout_seconds: float | None = Field(default=None, ge=1, le=120)


def _validate_tools(tools: list[str]) -> list[str]:
    unknown = [t for t in tools if t not in TOOL_CATALOG]
    if unknown:
        raise ValueError(f"Unknown tools: {', '.join(unknown)}")
    if len(set(tools)) != len(tools):
        raise ValueError("Tools must be unique.")
    return tools


class AgentBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    system_prompt: str = Field(default="", max_length=20_000)
    tools: list[str] = Field(default_factory=lambda: list(TOOL_CATALOG))
    allowed_tools: list[str] = Field(default_factory=list)
    policy: AgentPolicyIn = Field(default_factory=AgentPolicyIn)

    @field_validator("tools", "allowed_tools")
    @classmethod
    def _check_tools(cls, v: list[str]) -> list[str]:
        return _validate_tools(v)


class AgentCreate(AgentBase):
    provider: Literal["simulated", "http"]
    provider_config: ProviderConfig = Field(default_factory=ProviderConfig)
    auth_token: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def _check(self) -> AgentCreate:
        _validate_provider(self.provider, self.provider_config)
        if not set(self.allowed_tools) <= set(self.tools):
            raise ValueError("allowed_tools must be a subset of tools.")
        if self.provider == "simulated" and self.auth_token:
            raise ValueError("Simulated agents do not use an auth token.")
        return self


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    system_prompt: str | None = Field(default=None, max_length=20_000)
    tools: list[str] | None = None
    allowed_tools: list[str] | None = None
    policy: AgentPolicyIn | None = None
    provider_config: ProviderConfig | None = None
    auth_token: str | None = Field(default=None, max_length=4096)
    clear_auth_token: bool = False

    @field_validator("tools", "allowed_tools")
    @classmethod
    def _check_tools(cls, v: list[str] | None) -> list[str] | None:
        return v if v is None else _validate_tools(v)


def _validate_provider(provider: str, cfg: ProviderConfig) -> None:
    if provider == "simulated":
        if cfg.profile not in PROFILES:
            raise ValueError(f"Simulated agents need a profile: {', '.join(PROFILES)}.")
        if cfg.endpoint_url:
            raise ValueError("Simulated agents do not have an endpoint URL.")
    else:
        if not cfg.endpoint_url:
            raise ValueError("HTTP agents need an endpoint_url.")
        if cfg.profile:
            raise ValueError("HTTP agents do not have a simulated profile.")


class RunBrief(ORM):
    id: str
    status: str
    reliability_score: float | None
    passed: int
    failed: int
    errored: int
    total: int
    created_at: datetime
    completed_at: datetime | None


class AgentOut(ORM):
    id: str
    name: str
    description: str
    provider: str
    provider_config: dict[str, Any]
    system_prompt: str
    tools: list[str]
    allowed_tools: list[str]
    policy: dict[str, Any]
    has_auth_token: bool
    created_at: datetime
    updated_at: datetime
    latest_run: RunBrief | None = None


# ------------------------------------------------------------------ runs
class RunCreate(BaseModel):
    agent_id: str = Field(max_length=36)
    scenario_ids: list[str] | None = Field(default=None, max_length=100)


class RunOut(ORM):
    id: str
    agent_id: str
    agent_name: str
    status: str
    scenario_ids: list[str]
    total: int
    passed: int
    failed: int
    errored: int
    reliability_score: float | None
    critical_findings: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class FindingOut(ORM):
    id: str
    rule_id: str
    title: str
    severity: str
    category: str
    owasp_ref: str
    source: str
    explanation: str
    recommendation: str
    evidence: dict[str, Any]


class ResultSummary(ORM):
    id: str
    scenario_id: str
    scenario_name: str
    category: str
    severity: str
    status: str
    score: int
    metrics: dict[str, Any]
    error: str | None
    expectations: list[dict[str, Any]]
    findings: list[FindingOut]


class ResultDetail(ResultSummary):
    trace: list[dict[str, Any]]
    sandbox_effects: dict[str, Any]


class RunDetail(RunOut):
    agent_snapshot: dict[str, Any]
    results: list[ResultSummary]
    disclaimer: str = DISCLAIMER
