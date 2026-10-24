"""Read-only catalogue: sandbox tools, scenarios, reference agent profiles, policy rules."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import current_user
from app.engine.agents.simulated import PROFILES
from app.engine.policy import RULES
from app.engine.sandbox import TOOL_CATALOG
from app.engine.scenarios import CATEGORY_LABELS, SCENARIOS, get_scenario
from app.engine.types import OWASP_REF

router = APIRouter(tags=["catalog"], dependencies=[Depends(current_user)])


@router.get("/tools")
def list_tools() -> list[dict]:
    return [{**spec.schema(), "category": spec.category} for spec in TOOL_CATALOG.values()]


@router.get("/scenarios")
def list_scenarios() -> dict:
    return {
        "categories": [{"id": c.value, "label": label} for c, label in CATEGORY_LABELS.items()],
        "scenarios": [s.to_summary() for s in SCENARIOS],
    }


@router.get("/scenarios/{scenario_id}")
def scenario_detail(scenario_id: str) -> dict:
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scenario not found.")
    return scenario.to_detail()


@router.get("/profiles")
def list_profiles() -> list[dict]:
    return [{"id": k, "label": b.label, "description": b.description} for k, b in PROFILES.items()]


@router.get("/rules")
def list_rules() -> list[dict]:
    return [
        {
            "id": r.id,
            "title": r.title,
            "severity": r.severity.value,
            "category": r.category.value,
            "owasp_ref": OWASP_REF[r.category],
            "recommendation": r.recommendation,
        }
        for r in RULES.values()
    ]
