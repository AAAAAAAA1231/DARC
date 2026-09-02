from backend.core.parsing import parse_decimal, parse_timestamp


def test_ms_and_iso_timestamps():
    a = parse_timestamp(1_700_000_000_000)
    b = parse_timestamp("2024-01-02T03:04:05Z")
    assert a is not None and a.tzinfo is not None
    assert b is not None and b.year == 2024


def test_decimal_invalid_none():
    assert parse_decimal("not-a-number") is None
    assert parse_decimal("1.25") is not None
