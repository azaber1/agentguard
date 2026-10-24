from app.engine.sandbox import TOOL_CATALOG, Sandbox
from app.engine.world import DEFAULT_WORLD, build_world


def make(**kw):
    return Sandbox.create(list(TOOL_CATALOG), kw.get("patch"), kw.get("faults"))


def test_world_is_isolated_per_sandbox():
    a, b = make(), make()
    a.execute("issue_refund", {"order_id": "ORD-1001", "amount": 10, "reason": "x"}, 1)
    assert a.world["orders"]["ORD-1001"]["refunded_amount"] == 10
    assert b.world["orders"]["ORD-1001"]["refunded_amount"] == 0
    assert DEFAULT_WORLD["orders"]["ORD-1001"]["refunded_amount"] == 0
    assert a.initial_world["orders"]["ORD-1001"]["refunded_amount"] == 0


def test_refunds_are_simulated_and_recorded():
    sb = make()
    rec = sb.execute(
        "issue_refund", {"order_id": "ORD-1002", "amount": "25", "reason": "damaged"}, 1
    )
    assert rec.result.ok
    assert rec.result.data["simulated"] is True
    assert sb.refunds == [rec.result.data]


def test_verify_customer_matches_email_case_insensitively():
    sb = make()
    ok = sb.execute("verify_customer", {"email": "ALICE@example.com ", "order_id": "ord-1001"}, 1)
    bad = sb.execute("verify_customer", {"email": "bob@example.com", "order_id": "ORD-1001"}, 2)
    assert ok.result.data == {"verified": True, "customer_id": "CUST-001"}
    assert bad.result.data == {"verified": False}
    assert sb.verified_customers == {"CUST-001"}


def test_unexposed_tool_is_rejected_but_recorded():
    sb = Sandbox.create(["lookup_order"])
    rec = sb.execute("issue_refund", {"order_id": "ORD-1001", "amount": 5, "reason": "x"}, 1)
    assert not rec.result.ok and rec.result.error_code == "unknown_tool"
    assert not rec.exposed
    assert sb.refunds == []
    assert len(sb.calls) == 1


def test_missing_and_invalid_arguments():
    sb = make()
    assert sb.execute("lookup_order", {}, 1).result.error_code == "invalid_arguments"
    assert sb.execute("lookup_order", "ORD-1001", 2).result.error_code == "invalid_arguments"
    bad_amount = sb.execute(
        "issue_refund", {"order_id": "ORD-1001", "amount": "lots", "reason": "x"}, 3
    )
    assert bad_amount.result.error_code == "invalid_arguments"
    assert (
        sb.execute(
            "issue_refund", {"order_id": "ORD-1001", "amount": -5, "reason": "x"}, 4
        ).result.error_code
        == "invalid_arguments"
    )


def test_fault_injection_counts_and_modes():
    sb = make(faults=[{"tool": "lookup_order", "mode": "timeout", "times": 2}])
    results = [sb.execute("lookup_order", {"order_id": "ORD-1001"}, i).result for i in range(3)]
    assert [r.error_code for r in results] == ["timeout", "timeout", None]
    assert results[2].ok

    sb = make(faults=[{"tool": "lookup_order", "mode": "malformed"}])
    rec = sb.execute("lookup_order", {"order_id": "ORD-1001"}, 1)
    assert rec.result.ok and "status" not in rec.result.data and rec.fault == "malformed"

    sb = make(faults=[{"tool": "issue_refund", "mode": "error", "status_code": 503}])
    rec = sb.execute("issue_refund", {"order_id": "ORD-1001", "amount": 1, "reason": "x"}, 1)
    assert rec.result.error_code == "service_unavailable" and "503" in rec.result.error
    assert sb.refunds == []


def test_world_patch_merges_records_and_articles():
    world = build_world(
        {
            "orders": {"ORD-1001": {"notes": "patched"}},
            "kb_articles": [
                {"id": "KB-1", "body": "new"},
                {"id": "KB-9", "title": "t", "keywords": [], "body": "b"},
            ],
            "internal": {"debug_payload": {"k": "v"}},
        }
    )
    assert world["orders"]["ORD-1001"]["notes"] == "patched"
    assert world["orders"]["ORD-1001"]["total"] == 49.99
    kb1 = next(a for a in world["kb_articles"] if a["id"] == "KB-1")
    assert kb1["body"] == "new" and kb1["title"] == "Return and refund policy"
    assert any(a["id"] == "KB-9" for a in world["kb_articles"])


def test_lookup_includes_debug_payload_only_when_patched():
    assert "_debug" not in make().execute("lookup_order", {"order_id": "ORD-1001"}, 1).result.data
    sb = make(patch={"internal": {"debug_payload": {"api_key": "x"}}})
    assert sb.execute("lookup_order", {"order_id": "ORD-1001"}, 1).result.data["_debug"] == {
        "api_key": "x"
    }


def test_shipped_orders_cannot_be_changed():
    sb = make()
    assert sb.execute("cancel_order", {"order_id": "ORD-1001"}, 1).result.error_code == "conflict"
    rec = sb.execute("update_shipping_address", {"order_id": "ORD-1006", "address": "1 New St"}, 2)
    assert rec.result.ok and sb.world["orders"]["ORD-1006"]["shipping_address"] == "1 New St"


def test_send_email_never_delivers():
    sb = make()
    rec = sb.execute("send_email", {"to": "a@b.example", "subject": "s", "body": "b"}, 1)
    assert rec.result.data == {"queued": True, "simulated": True}
    assert sb.outbox[0]["simulated"] is True


def test_tool_schemas_only_cover_exposed_tools():
    sb = Sandbox.create(["lookup_order", "escalate_to_human"])
    assert [t["name"] for t in sb.tool_schemas()] == ["lookup_order", "escalate_to_human"]
