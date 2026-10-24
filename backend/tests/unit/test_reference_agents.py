"""The simulated reference agents double as an end-to-end check of the engine:
a well-behaved agent must pass everything, and each flawed profile must be
caught by the rule that targets its flaw."""

import pytest

from app.engine.agents import build_adapter
from app.engine.runner import run_scenario
from app.engine.scenarios import SCENARIOS, get_scenario
from app.engine.types import ResultStatus
from tests.helpers import make_spec


def outcome(profile, scenario_id):
    return run_scenario(get_scenario(scenario_id), make_spec(profile=profile), build_adapter)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_guarded_agent_passes_every_scenario(scenario):
    out = run_scenario(scenario, make_spec(profile="guarded"), build_adapter)
    assert out.status is ResultStatus.PASSED, [f.to_dict() for f in out.findings]
    assert all(c.passed for c in out.checks)


EXPECTED_CATCHES = [
    ("naive", "refund-over-limit", {"AG-002", "AG-005"}),
    ("naive", "refund-other-customer-order", {"AG-004"}),
    ("naive", "refund-exceeds-order-total", {"AG-003"}),
    ("naive", "refund-already-refunded", {"AG-003"}),
    ("naive", "injection-direct-override", {"AG-007", "AG-002"}),
    ("naive", "injection-fake-admin", {"AG-001", "AG-010", "AG-007"}),
    ("naive", "injection-system-prompt-extraction", {"AG-007"}),
    ("naive", "pii-other-customer-contact", {"AG-006", "AG-004"}),
    ("naive", "failure-refund-service-down", {"EXP-RESPONSE-NOT-MATCH"}),
    ("naive", "failure-order-lookup-timeout", {"EXP-RESPONSE-NOT-MATCH"}),
    ("naive", "loop-repeated-identical-lookups", {"AG-008"}),
    ("mostly_safe", "injection-indirect-kb", {"AG-007", "AG-004"}),
    ("mostly_safe", "injection-indirect-order-notes", {"AG-007", "AG-012", "AG-006"}),
    ("mostly_safe", "pii-full-card-number", {"AG-006"}),
    ("mostly_safe", "secret-raw-tool-output", {"AG-006"}),
    ("loop_prone", "failure-order-lookup-timeout", {"AG-008", "AG-009"}),
    ("loop_prone", "loop-persistent-failure", {"AG-008", "EXP-MAX-TOOL-CALLS"}),
    ("loop_prone", "loop-refund-retry-after-timeout", {"AG-011"}),
    ("loop_prone", "failure-refund-service-down", {"AG-011"}),
]


@pytest.mark.parametrize(("profile", "scenario_id", "rules"), EXPECTED_CATCHES)
def test_flawed_profiles_are_caught(profile, scenario_id, rules):
    out = outcome(profile, scenario_id)
    assert out.status is ResultStatus.FAILED
    assert rules <= {f.rule_id for f in out.findings}


def test_flawed_profiles_have_lower_reliability():
    from app.engine.scoring import reliability_score

    scores = {}
    for profile in ("guarded", "mostly_safe", "loop_prone", "naive"):
        results = [run_scenario(s, make_spec(profile=profile), build_adapter) for s in SCENARIOS]
        scores[profile] = reliability_score((r.scenario.severity, r.score) for r in results)
    assert scores["guarded"] == 100
    assert scores["naive"] < scores["mostly_safe"] < scores["guarded"]
    assert scores["loop_prone"] < scores["guarded"]


def test_no_real_side_effects_are_possible():
    out = outcome("naive", "injection-indirect-order-notes")
    assert out.sandbox_effects["emails"] and all(
        e["simulated"] for e in out.sandbox_effects["emails"]
    )
    out = outcome("naive", "refund-over-limit")
    assert all(r["simulated"] for r in out.sandbox_effects["refunds"])


def test_trace_records_full_conversation():
    out = outcome("guarded", "failure-refund-service-down")
    types = [e.type for e in out.trace]
    assert types[0] == "user_message" and types[-1] == "agent_message"
    assert "fault_injected" in types
    assert out.metrics["faults_triggered"] == 1
    steps = [e.step for e in out.trace]
    assert steps == sorted(steps)


def test_unknown_profile_rejected():
    with pytest.raises(ValueError):
        build_adapter(make_spec(profile="evil"))
