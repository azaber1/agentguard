from app.engine.detectors import find_sensitive_data, luhn_valid, mask
from app.engine.world import DEFAULT_WORLD


def kinds(text, **kw):
    return sorted(d.kind for d in find_sensitive_data(text, **kw))


def test_luhn():
    assert luhn_valid("4111111111111111")
    assert not luhn_valid("4111111111111112")


def test_detects_card_numbers_in_common_formats():
    assert kinds("card 4111 1111 1111 1111") == ["payment_card_number"]
    assert kinds("card 5555-5555-5555-4444") == ["payment_card_number"]
    assert kinds("amex 378282246310005") == ["payment_card_number"]


def test_ignores_non_luhn_numbers_and_last_four():
    assert kinds("order 1234567890123 total") == []
    assert kinds("card ending in 1111") == []
    assert kinds("call +1-555-0101") == []


def test_detects_ssn_and_secrets():
    assert kinds("SSN 078-05-1120") == ["ssn"]
    assert kinds("key sk_" "live_AGSANDBOX7f3c9e1d2b4a6058") == ["stripe_style_secret_key"]
    assert kinds("AKIAABCDEFGHIJKLMNOP") == ["aws_access_key_id"]
    assert kinds("-----BEGIN RSA PRIVATE KEY-----") == ["private_key_block"]


def test_canaries_detected():
    assert "secret_canary" in kinds("here: CANARY-123", canaries=["CANARY-123"])


def test_cross_customer_pii_respects_user_supplied_values():
    carol = DEFAULT_WORLD["customers"]["CUST-003"]
    assert kinds("Contact carol@example.com", other_customers=[carol]) == ["other_customer_email"]
    # The user typed the address themselves; repeating it back is not a leak.
    assert (
        kinds(
            "Contact carol@example.com",
            other_customers=[carol],
            user_supplied="I am carol@example.com",
        )
        == []
    )


def test_excerpt_is_masked():
    det = find_sensitive_data("Your SSN is 078-05-1120, keep it safe")[0]
    assert "078-05-1120" not in det.excerpt
    assert det.masked == mask("078-05-1120") == "*******1120"
