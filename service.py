from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

import srs
from models import Problem

CURRENT_USER_ID = 1

DIFFICULTY_RANK = {"hard": 0, "medium": 1, "easy": 2}


def add_problem(
    session: Session,
    problem_id: str,
    problem_link: str,
    difficulty: str,
    problem_description: str,
    topics: list[str],
) -> Problem:
    existing = _get(session, problem_id)
    if existing is not None:
        raise ValueError(f"Problem '{problem_id}' already exists")

    problem = Problem(
        user_id=CURRENT_USER_ID,
        problem_id=problem_id,
        problem_link=problem_link,
        difficulty=_normalize_difficulty(difficulty),
        problem_description=problem_description,
        topics=topics,
        solved=False,
        mistakes="",
        interval_days=0,
        repetitions=0,
    )
    session.add(problem)
    session.flush()
    return problem


def record_attempt(
    session: Session,
    problem_id: str,
    solved: bool,
    mistakes: str | None,
    today: date | None = None,
) -> Problem:
    problem = _get(session, problem_id)
    if problem is None:
        raise ValueError(f"Problem '{problem_id}' not found")

    today = today or date.today()
    problem.solved = bool(solved)
    problem.last_solved = today
    if mistakes is not None:
        problem.mistakes = mistakes

    problem.interval_days = srs.next_interval(problem.difficulty, problem.repetitions, solved)
    if solved:
        problem.repetitions += 1
    else:
        problem.repetitions = 0
    session.flush()
    return problem


def get_due_problems(session: Session, today: date | None = None, limit: int = 10) -> list[Problem]:
    today = today or date.today()
    candidates = [
        p
        for p in session.scalars(
            select(Problem).where(Problem.user_id == CURRENT_USER_ID)
        ).all()
        if srs.is_due(p.last_solved, p.interval_days, p.solved, today)
    ]
    return sorted(candidates, key=lambda p: _priority(p, today))[:limit]


def get_backlog(session: Session) -> list[Problem]:
    return list(
        session.scalars(
            select(Problem)
            .where(Problem.user_id == CURRENT_USER_ID, Problem.solved == False)  # noqa: E712
            .order_by(Problem.id)
        ).all()
    )


def get_problem(session: Session, problem_id: str) -> Problem | None:
    return _get(session, problem_id)


def list_problems_by_topic(session: Session, topic: str) -> list[Problem]:
    problems = session.scalars(
        select(Problem).where(Problem.user_id == CURRENT_USER_ID)
    ).all()
    needle = topic.lower()
    return [p for p in problems if any(needle == t.lower() for t in (p.topics or []))]


def revision_stats(session: Session, today: date | None = None) -> dict:
    today = today or date.today()
    problems = session.scalars(
        select(Problem).where(Problem.user_id == CURRENT_USER_ID)
    ).all()
    solved = [p for p in problems if p.solved]
    due = [p for p in problems if srs.is_due(p.last_solved, p.interval_days, p.solved, today)]
    return {
        "total": len(problems),
        "solved": len(solved),
        "backlog": len(problems) - len(solved),
        "due_today": len(due),
        "by_difficulty": {
            d: sum(1 for p in problems if p.difficulty == d) for d in ("easy", "medium", "hard")
        },
    }


def _get(session: Session, problem_id: str) -> Problem | None:
    return session.scalars(
        select(Problem).where(
            Problem.user_id == CURRENT_USER_ID, Problem.problem_id == problem_id
        )
    ).first()


def _priority(p: Problem, today: date) -> tuple:
    has_mistakes = bool(p.mistakes.strip())
    return (
        -srs.overdue_days(p.last_solved, p.interval_days, today),
        DIFFICULTY_RANK.get(p.difficulty, 1),
        not has_mistakes,
        p.problem_id,
    )


def _normalize_difficulty(difficulty: str) -> str:
    d = (difficulty or "medium").lower()
    return d if d in DIFFICULTY_RANK else "medium"
