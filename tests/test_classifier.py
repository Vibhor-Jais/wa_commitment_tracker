from wa_commitment_tracker.classifier import classify_message_type, parse_hour, COMMITMENT, ACHIEVEMENT


def test_before_noon_24h():
    assert classify_message_type("08:03") == COMMITMENT
    assert classify_message_type("11:59") == COMMITMENT


def test_noon_and_after_24h():
    assert classify_message_type("12:00") == ACHIEVEMENT
    assert classify_message_type("18:30") == ACHIEVEMENT


def test_12h_with_am_pm():
    assert classify_message_type("8:03 AM") == COMMITMENT
    assert classify_message_type("11:59 AM") == COMMITMENT
    assert classify_message_type("12:00 PM") == ACHIEVEMENT
    assert classify_message_type("6:30 PM") == ACHIEVEMENT


def test_midnight_counts_as_before_noon():
    assert classify_message_type("12:00 AM") == COMMITMENT
    assert classify_message_type("00:00") == COMMITMENT


def test_ios_style_with_seconds():
    assert classify_message_type("8:03:15 AM") == COMMITMENT
    assert classify_message_type("1:03:15 PM") == ACHIEVEMENT


def test_unparseable_time_returns_none():
    assert classify_message_type("not a time") is None
    assert parse_hour("not a time") is None
