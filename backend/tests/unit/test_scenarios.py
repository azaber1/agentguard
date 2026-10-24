import re
from collections import Counter

import pytest

from app.engine.sandbox import TOOL_CATALOG
from app.engine.scenarios import SCENARIOS, ScenarioCategory, get_scenario
from app.engine.world import build_world


def test_library_has_at_least_20_unique_scenarios():
    assert len(SCENARIOS) >= 20
    assert len({s.id for s in SCENARIOS}) == len(SCENARIOS)


def test_every_required_category_is_covered():
    counts = Counter(s.category for s in SCENARIOS)
    for category in ScenarioCategory:
        assert counts[category] >= 3, category


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_scenario_is_well_formed(scenario):
    assert scenario.user_turns and all(t.strip() for t in scenario.user_turns)
    exp = scenario.expectations
    for tool in (*exp.required_tools, *exp.forbidden_tools):
        assert tool in TOOL_CATALOG
    assert not set(exp.required_tools) & set(exp.forbidden_tools)
    for pattern in (*exp.response_must_match, *exp.response_must_not_match):
        re.compile(pattern)
    for fault in scenario.faults:
        assert fault["tool"] in TOOL_CATALOG and fault["mode"] in ("error", "timeout", "malformed")
    world = build_world(scenario.world_patch)
    if scenario.persona.customer_id:
        assert scenario.persona.customer_id in world["customers"]
    detail = scenario.to_detail()
    assert detail["id"] == scenario.id and detail["category_label"]


def test_get_scenario():
    assert get_scenario("refund-over-limit").name == "Refund above agent limit"
    assert get_scenario("nope") is None
