from backend.core.enums import SecurityVerdict
from backend.services.security import can_enter_recommendation_pool, evaluate_goplus, native_protocol_scan


def test_honeypot_is_malicious_and_blocked():
    result = evaluate_goplus({"is_honeypot": "1", "is_open_source": "1"})
    assert result["verdict"] == SecurityVerdict.MALICIOUS.value
    assert result["blocked"] is True
    assert not can_enter_recommendation_pool(result["verdict"])


def test_unknown_not_safe():
    assert not can_enter_recommendation_pool(SecurityVerdict.UNKNOWN.value)
    assert can_enter_recommendation_pool(SecurityVerdict.SAFE.value)
    assert can_enter_recommendation_pool(SecurityVerdict.NATIVE_PROTOCOL.value)
    assert not can_enter_recommendation_pool(SecurityVerdict.HIGH_RISK.value)


def test_native_protocol_not_unknown():
    scan = native_protocol_scan("PROJECT-X", "BTC")
    assert scan["verdict"] == SecurityVerdict.NATIVE_PROTOCOL.value
    assert scan["blocked"] is False
