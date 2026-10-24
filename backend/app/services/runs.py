"""Creating, executing and reporting on test runs."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import SecretBox
from app.engine.runner import AdapterFactory, run_scenario
from app.engine.scenarios import CATEGORY_LABELS, SCENARIOS, ScenarioCategory, get_scenario
from app.engine.scoring import reliability_score
from app.engine.types import AgentPolicy, AgentSpec, ResultStatus, Severity
from app.models import Agent, FindingRecord, ScenarioResult, TestRun
from app.schemas import DISCLAIMER

log = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "running")


def agent_snapshot(agent: Agent) -> dict[str, Any]:
    """Immutable copy of the agent's configuration at run time. Never includes secrets."""
    return {
        "id": agent.id,
        "name": agent.name,
        "provider": agent.provider,
        "provider_config": dict(agent.provider_config),
        "system_prompt": agent.system_prompt,
        "tools": list(agent.tools),
        "allowed_tools": list(agent.allowed_tools),
        "policy": AgentPolicy.from_dict(agent.policy).to_dict(),
        "has_auth_token": agent.auth_token_encrypted is not None,
    }


def spec_from_snapshot(snapshot: dict[str, Any], auth_token: str | None) -> AgentSpec:
    return AgentSpec(
        name=snapshot["name"],
        provider=snapshot["provider"],
        system_prompt=snapshot["system_prompt"],
        tools=tuple(snapshot["tools"]),
        allowed_tools=tuple(snapshot["allowed_tools"]),
        policy=AgentPolicy.from_dict(snapshot["policy"]),
        provider_config=snapshot["provider_config"],
        auth_token=auth_token,
    )


def resolve_scenarios(scenario_ids: list[str] | None) -> list[str]:
    if not scenario_ids:
        return [s.id for s in SCENARIOS]
    unknown = [s for s in scenario_ids if get_scenario(s) is None]
    if unknown:
        raise ValueError(f"Unknown scenarios: {', '.join(unknown)}")
    return list(dict.fromkeys(scenario_ids))


def create_run(db: Session, agent: Agent, scenario_ids: list[str], user_id: str | None) -> TestRun:
    run = TestRun(
        org_id=agent.org_id,
        agent_id=agent.id,
        status="queued",
        scenario_ids=scenario_ids,
        agent_snapshot=agent_snapshot(agent),
        total=len(scenario_ids),
        created_by=user_id,
    )
    db.add(run)
    db.commit()
    return run


def execute_run(
    run_id: str,
    factory: sessionmaker[Session],
    secret_box: SecretBox,
    adapter_factory: AdapterFactory,
) -> None:
    """Execute a queued run. Commits after each scenario so progress is visible."""
    with factory() as db:
        run = db.get(TestRun, run_id)
        if run is None or run.status != "queued":
            return
        run.status = "running"
        run.started_at = datetime.now(UTC)
        db.commit()
        try:
            agent = db.get(Agent, run.agent_id)
            token = (
                secret_box.decrypt(agent.auth_token_encrypted)
                if agent is not None and agent.auth_token_encrypted
                else None
            )
            spec = spec_from_snapshot(run.agent_snapshot, token)
            scored: list[tuple[Severity, int]] = []
            for position, scenario_id in enumerate(run.scenario_ids):
                scenario = get_scenario(scenario_id)
                assert scenario is not None
                outcome = run_scenario(scenario, spec, adapter_factory)
                result = ScenarioResult(
                    run_id=run.id,
                    org_id=run.org_id,
                    position=position,
                    scenario_id=scenario.id,
                    scenario_name=scenario.name,
                    category=scenario.category.value,
                    severity=scenario.severity.value,
                    status=outcome.status.value,
                    score=outcome.score,
                    expectations=[c.to_dict() for c in outcome.checks],
                    trace=[e.to_dict() for e in outcome.trace],
                    metrics=outcome.metrics,
                    sandbox_effects=outcome.sandbox_effects,
                    error=outcome.error,
                )
                result.findings = [
                    FindingRecord(
                        run_id=run.id,
                        org_id=run.org_id,
                        position=i,
                        rule_id=f.rule_id,
                        title=f.title,
                        severity=f.severity.value,
                        category=f.category.value,
                        owasp_ref=f.owasp_ref,
                        source=f.source,
                        explanation=f.explanation,
                        recommendation=f.recommendation,
                        evidence=f.evidence,
                    )
                    for i, f in enumerate(outcome.findings)
                ]
                db.add(result)
                run.passed += outcome.status is ResultStatus.PASSED
                run.failed += outcome.status is ResultStatus.FAILED
                run.errored += outcome.status is ResultStatus.ERROR
                run.critical_findings += sum(
                    f.severity is Severity.CRITICAL for f in outcome.findings
                )
                scored.append((scenario.severity, outcome.score))
                db.commit()
            run.reliability_score = reliability_score(scored)
            run.status = "completed"
        except Exception:
            log.exception("Run %s failed", run_id)
            db.rollback()
            run = db.get(TestRun, run_id)
            assert run is not None
            run.status = "failed"
            run.error = "An internal error interrupted this run. Completed scenarios were kept."
        run.completed_at = datetime.now(UTC)
        db.commit()


def recover_interrupted_runs(db: Session) -> int:
    """Mark runs left active by a previous process as failed."""
    runs = db.scalars(select(TestRun).where(TestRun.status.in_(ACTIVE_STATUSES))).all()
    for run in runs:
        run.status = "failed"
        run.error = "The server restarted before this run finished."
        run.completed_at = datetime.now(UTC)
    db.commit()
    return len(runs)


def build_report(run: TestRun) -> dict[str, Any]:
    """Full exportable report for a run, including traces."""
    findings = [f for r in run.results for f in r.findings]
    recs: dict[str, dict[str, Any]] = {}
    for f in findings:
        entry = recs.setdefault(
            f.rule_id,
            {
                "rule_id": f.rule_id,
                "title": f.title,
                "severity": f.severity,
                "category": f.category,
                "owasp_ref": f.owasp_ref,
                "recommendation": f.recommendation,
                "occurrences": 0,
                "scenarios": [],
            },
        )
        entry["occurrences"] += 1
        if f.result.scenario_id not in entry["scenarios"]:
            entry["scenarios"].append(f.result.scenario_id)
    order = {s.value: i for i, s in enumerate(Severity)}
    by_category: dict[str, dict[str, int]] = {}
    for r in run.results:
        c = by_category.setdefault(r.category, {"total": 0, "passed": 0})
        c["total"] += 1
        c["passed"] += r.status == "passed"
    return {
        "report_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": DISCLAIMER,
        "run": {
            "id": run.id,
            "status": run.status,
            "created_at": run.created_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "total": run.total,
            "passed": run.passed,
            "failed": run.failed,
            "errored": run.errored,
            "reliability_score": run.reliability_score,
        },
        "agent": run.agent_snapshot,
        "risk_summary": {
            "by_severity": dict(Counter(f.severity for f in findings)),
            "by_category": dict(Counter(f.category for f in findings)),
        },
        "category_results": [
            {"category": k, "label": CATEGORY_LABELS[ScenarioCategory(k)], **v}
            for k, v in by_category.items()
        ],
        "recommendations": sorted(
            recs.values(), key=lambda e: (order[e["severity"]], -e["occurrences"])
        ),
        "results": [
            {
                "scenario_id": r.scenario_id,
                "scenario_name": r.scenario_name,
                "category": r.category,
                "severity": r.severity,
                "status": r.status,
                "score": r.score,
                "error": r.error,
                "metrics": r.metrics,
                "expectations": r.expectations,
                "findings": [
                    {
                        k: getattr(f, k)
                        for k in (
                            "rule_id",
                            "title",
                            "severity",
                            "category",
                            "owasp_ref",
                            "source",
                            "explanation",
                            "recommendation",
                            "evidence",
                        )
                    }
                    for f in r.findings
                ],
                "trace": r.trace,
                "sandbox_effects": r.sandbox_effects,
            }
            for r in run.results
        ],
    }
