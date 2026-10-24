"""Agent registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import Settings, get_settings
from app.core.security import SecretBox
from app.db.session import get_db
from app.engine.netguard import UnsafeURLError, validate_agent_url
from app.models import Agent, TestRun, User
from app.schemas import AgentCreate, AgentOut, AgentUpdate, RunBrief, _validate_provider

router = APIRouter(prefix="/agents", tags=["agents"])


def get_org_agent(db: Session, user: User, agent_id: str) -> Agent:
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id, Agent.org_id == user.org_id, Agent.is_archived.is_(False)
        )
    )
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found.")
    return agent


def _check_endpoint(agent_provider: str, url: str | None, settings: Settings) -> None:
    if agent_provider == "http" and url:
        try:
            validate_agent_url(url, allow_private=settings.allow_private_agent_urls, resolve=False)
        except UnsafeURLError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


def to_out(db: Session, agent: Agent) -> AgentOut:
    latest = db.scalar(
        select(TestRun)
        .where(TestRun.agent_id == agent.id)
        .order_by(TestRun.created_at.desc())
        .limit(1)
    )
    out = AgentOut.model_validate(
        {
            **{k: getattr(agent, k) for k in AgentOut.model_fields if hasattr(agent, k)},
            "has_auth_token": agent.auth_token_encrypted is not None,
            "latest_run": RunBrief.model_validate(latest) if latest else None,
        }
    )
    return out


def _box(request: Request) -> SecretBox:
    return request.app.state.secret_box


@router.get("", response_model=list[AgentOut])
def list_agents(
    db: Session = Depends(get_db), user: User = Depends(current_user)
) -> list[AgentOut]:
    agents = db.scalars(
        select(Agent)
        .where(Agent.org_id == user.org_id, Agent.is_archived.is_(False))
        .order_by(Agent.created_at.desc())
    ).all()
    return [to_out(db, a) for a in agents]


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(
    body: AgentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> AgentOut:
    _check_endpoint(body.provider, body.provider_config.endpoint_url, settings)
    agent = Agent(
        org_id=user.org_id,
        name=body.name.strip(),
        description=body.description,
        provider=body.provider,
        provider_config=body.provider_config.model_dump(exclude_none=True),
        system_prompt=body.system_prompt,
        tools=body.tools,
        allowed_tools=body.allowed_tools,
        policy=body.policy.model_dump(),
        auth_token_encrypted=_box(request).encrypt(body.auth_token) if body.auth_token else None,
        created_by=user.id,
    )
    db.add(agent)
    db.commit()
    return to_out(db, agent)


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> AgentOut:
    return to_out(db, get_org_agent(db, user, agent_id))


@router.patch("/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: str,
    body: AgentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> AgentOut:
    agent = get_org_agent(db, user, agent_id)
    data = body.model_dump(exclude_unset=True, exclude={"auth_token", "clear_auth_token"})
    if "provider_config" in data and body.provider_config is not None:
        try:
            _validate_provider(agent.provider, body.provider_config)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        _check_endpoint(agent.provider, body.provider_config.endpoint_url, settings)
        data["provider_config"] = body.provider_config.model_dump(exclude_none=True)
    tools = data.get("tools", agent.tools)
    allowed = data.get("allowed_tools", agent.allowed_tools)
    if "tools" in data and "allowed_tools" not in data:
        allowed = [t for t in allowed if t in tools]
        data["allowed_tools"] = allowed
    if not set(allowed) <= set(tools):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "allowed_tools must be a subset of tools."
        )
    for key, value in data.items():
        if value is not None:
            setattr(agent, key, value.strip() if key == "name" else value)
    if body.clear_auth_token:
        agent.auth_token_encrypted = None
    elif body.auth_token:
        if agent.provider != "http":
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Simulated agents do not use an auth token."
            )
        agent.auth_token_encrypted = _box(request).encrypt(body.auth_token)
    db.commit()
    return to_out(db, agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_agent(
    agent_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> None:
    agent = get_org_agent(db, user, agent_id)
    agent.is_archived = True
    agent.auth_token_encrypted = None
    db.commit()
