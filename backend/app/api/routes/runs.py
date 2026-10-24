"""Test runs and reports."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.routes.agents import get_org_agent
from app.db.session import get_db
from app.models import Agent, ScenarioResult, TestRun, User
from app.schemas import ResultDetail, RunCreate, RunDetail, RunOut
from app.services.runs import (
    ACTIVE_STATUSES,
    build_report,
    create_run,
    execute_run,
    resolve_scenarios,
)

router = APIRouter(prefix="/runs", tags=["runs"])


def _run_out(run: TestRun) -> dict:
    return {
        **{c: getattr(run, c) for c in RunOut.model_fields if hasattr(run, c)},
        "agent_name": run.agent_snapshot["name"],
    }


def get_org_run(db: Session, user: User, run_id: str, *, with_results: bool = False) -> TestRun:
    query = select(TestRun).where(TestRun.id == run_id, TestRun.org_id == user.org_id)
    if with_results:
        query = query.options(selectinload(TestRun.results).selectinload(ScenarioResult.findings))
    run = db.scalar(query)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found.")
    return run


@router.post("", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
def start_run(
    body: RunCreate,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    agent = get_org_agent(db, user, body.agent_id)
    try:
        scenario_ids = resolve_scenarios(body.scenario_ids)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    active = db.scalar(
        select(TestRun.id).where(TestRun.agent_id == agent.id, TestRun.status.in_(ACTIVE_STATUSES))
    )
    if active:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A run for this agent is already in progress."
        )
    run = create_run(db, agent, scenario_ids, user.id)
    state = request.app.state
    background.add_task(
        execute_run, run.id, state.session_factory, state.secret_box, state.adapter_factory
    )
    return _run_out(run)


@router.get("", response_model=list[RunOut])
def list_runs(
    agent_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[dict]:
    query = (
        select(TestRun)
        .join(Agent)
        .where(TestRun.org_id == user.org_id, Agent.is_archived.is_(False))
    )
    if agent_id:
        query = query.where(TestRun.agent_id == agent_id)
    runs = db.scalars(query.order_by(TestRun.created_at.desc()).limit(limit).offset(offset)).all()
    return [_run_out(r) for r in runs]


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    run = get_org_run(db, user, run_id, with_results=True)
    return {**_run_out(run), "agent_snapshot": run.agent_snapshot, "results": run.results}


@router.get("/{run_id}/results/{result_id}", response_model=ResultDetail)
def get_result(
    run_id: str, result_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> ScenarioResult:
    result = db.scalar(
        select(ScenarioResult)
        .where(
            ScenarioResult.id == result_id,
            ScenarioResult.run_id == run_id,
            ScenarioResult.org_id == user.org_id,
        )
        .options(selectinload(ScenarioResult.findings))
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Result not found.")
    return result


@router.get("/{run_id}/report")
def get_report(
    run_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict:
    run = get_org_run(db, user, run_id, with_results=True)
    if run.status in ACTIVE_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "The run is still in progress.")
    return build_report(run)
