"""Organization-level dashboard aggregates."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.db.session import get_db
from app.engine.scenarios import CATEGORY_LABELS, ScenarioCategory
from app.models import Agent, FindingRecord, ScenarioResult, TestRun, User
from app.schemas import DISCLAIMER

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    org = user.org_id
    live_runs = (
        select(TestRun.id).join(Agent).where(TestRun.org_id == org, Agent.is_archived.is_(False))
    )

    status_counts = dict(
        db.execute(
            select(ScenarioResult.status, func.count())
            .where(ScenarioResult.run_id.in_(live_runs))
            .group_by(ScenarioResult.status)
        ).all()
    )
    executed = sum(status_counts.values())
    passed = status_counts.get("passed", 0)

    # Policy findings are security/compliance violations; expectation findings are not counted.
    is_violation = (FindingRecord.run_id.in_(live_runs), FindingRecord.source == "policy")
    by_severity = dict(
        db.execute(
            select(FindingRecord.severity, func.count())
            .where(*is_violation)
            .group_by(FindingRecord.severity)
        ).all()
    )
    by_category = dict(
        db.execute(
            select(FindingRecord.category, func.count())
            .where(*is_violation)
            .group_by(FindingRecord.category)
        ).all()
    )
    top_rules = [
        {"rule_id": rule_id, "title": title, "count": n}
        for rule_id, title, n in db.execute(
            select(FindingRecord.rule_id, FindingRecord.title, func.count().label("n"))
            .where(*is_violation)
            .group_by(FindingRecord.rule_id, FindingRecord.title)
            .order_by(func.count().desc())
            .limit(5)
        ).all()
    ]

    category_rows = db.execute(
        select(ScenarioResult.category, ScenarioResult.status, func.count())
        .where(ScenarioResult.run_id.in_(live_runs))
        .group_by(ScenarioResult.category, ScenarioResult.status)
    ).all()
    categories: dict[str, dict[str, int]] = {}
    for category, st, n in category_rows:
        c = categories.setdefault(category, {"total": 0, "passed": 0})
        c["total"] += n
        if st == "passed":
            c["passed"] += n

    agents = db.scalars(
        select(Agent).where(Agent.org_id == org, Agent.is_archived.is_(False)).order_by(Agent.name)
    ).all()
    agent_rows = []
    latest_scores = []
    for agent in agents:
        latest = db.scalar(
            select(TestRun)
            .where(TestRun.agent_id == agent.id, TestRun.status == "completed")
            .order_by(TestRun.completed_at.desc())
            .limit(1)
        )
        if latest and latest.reliability_score is not None:
            latest_scores.append(latest.reliability_score)
        agent_rows.append(
            {
                "id": agent.id,
                "name": agent.name,
                "provider": agent.provider,
                "latest_run": None
                if latest is None
                else {
                    "id": latest.id,
                    "reliability_score": latest.reliability_score,
                    "passed": latest.passed,
                    "total": latest.total,
                    "critical_findings": latest.critical_findings,
                    "completed_at": latest.completed_at,
                },
            }
        )

    recent = db.scalars(
        live_runs.with_only_columns(TestRun).order_by(TestRun.created_at.desc()).limit(8)
    ).all()
    return {
        "totals": {
            "runs": db.scalar(select(func.count()).select_from(live_runs.subquery())),
            "agents": len(agents),
            "tests_executed": executed,
            "passed": passed,
            "failed": status_counts.get("failed", 0),
            "errored": status_counts.get("error", 0),
            "pass_rate": round(100 * passed / executed, 1) if executed else None,
        },
        "reliability_score": round(sum(latest_scores) / len(latest_scores), 1)
        if latest_scores
        else None,
        "security_violations": {
            "total": sum(by_severity.values()),
            "by_severity": by_severity,
            "by_category": by_category,
            "top_rules": top_rules,
        },
        "category_results": [
            {"category": k, "label": CATEGORY_LABELS[ScenarioCategory(k)], **v}
            for k, v in sorted(categories.items())
        ],
        "agents": agent_rows,
        "recent_runs": [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "agent_name": r.agent_snapshot["name"],
                "status": r.status,
                "passed": r.passed,
                "failed": r.failed,
                "errored": r.errored,
                "total": r.total,
                "reliability_score": r.reliability_score,
                "created_at": r.created_at,
            }
            for r in recent
        ],
        "disclaimer": DISCLAIMER,
    }
