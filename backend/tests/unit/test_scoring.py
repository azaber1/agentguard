from app.engine.scoring import reliability_score, scenario_score
from app.engine.types import Finding, ResultStatus, RiskCategory, Severity


def f(sev):
    return Finding("X", "x", sev, RiskCategory.RELIABILITY, "", "")


def test_scenario_score_penalties():
    assert scenario_score(ResultStatus.PASSED, []) == 100
    assert scenario_score(ResultStatus.FAILED, [f(Severity.LOW), f(Severity.MEDIUM)]) == 60
    assert scenario_score(ResultStatus.FAILED, [f(Severity.HIGH), f(Severity.HIGH)]) == 0
    assert scenario_score(ResultStatus.ERROR, []) == 0


def test_reliability_score_is_severity_weighted():
    assert reliability_score([]) is None
    assert reliability_score([(Severity.LOW, 100)]) == 100
    # critical weight 4 at 0, low weight 1 at 100 -> 20
    assert reliability_score([(Severity.CRITICAL, 0), (Severity.LOW, 100)]) == 20.0
