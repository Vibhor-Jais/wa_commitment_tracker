from wa_commitment_tracker.splitter import split_export


def test_ios_left_to_right_mark_does_not_break_header_or_field_parsing():
    """Regression test: iOS WhatsApp exports prepend an invisible U+200E
    (left-to-right mark) to every line, including continuation lines. Left
    unstripped, this broke header matching entirely (the line no longer
    visibly starts with "[") so split_export() silently yielded zero
    messages, and it also corrupted field lines like "CA noa:- 1" for
    downstream parsing."""
    export_text = (
        "‎[12/09/2026, 8:05:00 AM] Asha Rao: Good morning Team,\n"
        "‎CA noa:- 1\n"
        "SA noa:- 2"
    )

    messages = list(split_export(export_text))

    assert len(messages) == 1
    date_str, time_str, sender, body = messages[0]
    assert date_str == "12/09/2026"
    assert time_str == "8:05:00 AM"
    assert sender == "Asha Rao"
    assert "‎" not in body
    assert "CA noa:- 1" in body
    assert "SA noa:- 2" in body
