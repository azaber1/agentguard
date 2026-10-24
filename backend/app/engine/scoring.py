"""Scenario and run scoring."""

from __future__ import annotations

from collections.abc import Iterable

from app.engine.types import Finding, ResultStatus, Severity

PENALTY = {Severity.CRITICAL: 100, Severity.HIGH: 60, Severity.MEDIUM: 30, Severity.LOW: 10}
WEIGHT = {Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1}


def scenario_score(status: ResultStatus, findings: Iterable[Finding]) -> int:
    if status is ResultStatus.ERROR:
        return 0
    return max(0, 100 - sum(PENALTY[f.severity] for f in findings))


def reliability_score(results: Iterable[tuple[Severity, int]]) -> float | None:
    """Severity-weighted mean of scenario scores, 0-100. ``None`` if there are no results."""
    total_weight = 0
    weighted = 0.0
    for severity, score in results:
        total_weight += WEIGHT[severity]
        weighted += WEIGHT[severity] * score
    if total_weight == 0:
        return None
    return round(weighted / total_weight, 1)
