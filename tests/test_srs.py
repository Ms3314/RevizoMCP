from datetime import date, timedelta

from app import srs


def test_first_success_uses_first_rung():
    assert srs.next_interval("medium", 0, True) == 1


def test_success_advances_ladder():
    assert srs.next_interval("easy", 1, True) == 3
    assert srs.next_interval("easy", 2, True) == 7
    assert srs.next_interval("medium", 3, True) == 8
    assert srs.next_interval("hard", 2, True) == 3


def test_success_caps_at_last_rung():
    ladder = srs.INTERVAL_LADDERS["easy"]
    assert srs.next_interval("easy", 99, True) == ladder[-1]


def test_failure_resets_to_one_day():
    assert srs.next_interval("easy", 5, False) == 1
    assert srs.next_interval("hard", 0, False) == 1


def test_unknown_difficulty_falls_back_to_medium():
    assert srs.next_interval("??? ", 1, True) == srs.INTERVAL_LADDERS["medium"][1]
    assert srs.next_interval("", 0, True) == 1


def test_is_due_never_solved():
    assert srs.is_due(None, 0, False, date(2026, 9, 23))
    assert srs.is_due(None, 7, True, date(2026, 9, 23))


def test_is_due_interval_elapsed():
    last = date(2026, 9, 20)
    assert srs.is_due(last, 3, True, date(2026, 9, 23))
    assert not srs.is_due(last, 3, True, date(2026, 9, 22))


def test_overdue_days():
    last = date(2026, 9, 20)
    assert srs.overdue_days(last, 3, date(2026, 9, 25)) == 2
    assert srs.overdue_days(last, 10, date(2026, 9, 25)) == 0
    assert srs.overdue_days(None, 5, date(2026, 9, 25)) == 0


def test_next_due_date_matches_interval():
    today = date(2026, 9, 23)
    last = today - timedelta(days=srs.INTERVAL_LADDERS["medium"][2])
    assert srs.is_due(last, srs.INTERVAL_LADDERS["medium"][2], True, today)
