from datetime import date

INTERVAL_LADDERS: dict[str, list[int]] = {
    "easy": [1, 3, 7, 14, 30, 60, 120],
    "medium": [1, 2, 4, 8, 16, 35, 70],
    "hard": [1, 2, 3, 6, 12, 25, 50],
}

DEFAULT_LADDER = INTERVAL_LADDERS["medium"]


def ladder_for(difficulty: str) -> list[int]:
    return INTERVAL_LADDERS.get((difficulty or "").lower(), DEFAULT_LADDER)


def next_interval(difficulty: str, repetitions: int, solved: bool) -> int:
    """Return the next interval in days after an attempt.

    solved=True advances one rung on the difficulty ladder.
    solved=False resets to the first rung (re-attempt tomorrow).
    """
    ladder = ladder_for(difficulty)
    if not solved:
        return ladder[0]
    idx = max(repetitions, 0)
    return ladder[min(idx, len(ladder) - 1)]


def is_due(last_solved: date | None, interval_days: int, solved: bool, today: date) -> bool:
    """A problem is due when it was never solved or its interval has elapsed."""
    if not solved or last_solved is None:
        return True
    return today >= _add_days(last_solved, interval_days)


def overdue_days(last_solved: date | None, interval_days: int, today: date) -> int:
    """Days past the due date; 0 when not overdue or never scheduled."""
    if last_solved is None:
        return 0
    due = _add_days(last_solved, interval_days)
    return max((today - due).days, 0)


def _add_days(d: date, days: int) -> date:
    return date.fromordinal(d.toordinal() + days)
