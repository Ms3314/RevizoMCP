from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import srs
from app.models import Attempt, Problem

CURRENT_USER_ID = 1

DIFFICULTY_RANK = {"hard": 0, "medium": 1, "easy": 2}

MISTAKE_TAGS = frozenset(
    {
        "complexity_tle",
        "edge_cases",
        "off_by_one",
        "overflow",
        "misread_constraints",
        "wrong_ds",
        "math_error",
        "implementation_bug",
        "other",
    }
)


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
    mistake_tags: list[str] | None = None,
    today: date | None = None,
) -> dict:
    problem = _get(session, problem_id)
    if problem is None:
        raise ValueError(f"Problem '{problem_id}' not found")

    today = today or date.today()
    tags = _normalize_tags(mistake_tags)
    repeated_tags = _detect_repeated_tags(session, problem, tags)

    problem.solved = bool(solved)
    problem.last_solved = today
    if mistakes is not None:
        problem.mistakes = mistakes

    problem.interval_days = srs.next_interval(problem.difficulty, problem.repetitions, solved)
    if solved:
        problem.repetitions += 1
    else:
        problem.repetitions = 0

    session.add(
        Attempt(
            user_id=CURRENT_USER_ID,
            problem_pk=problem.id,
            attempt_date=today,
            solved=bool(solved),
            mistakes=mistakes or "",
            mistake_tags=tags,
        )
    )
    session.flush()
    return {"problem": problem, "repeated_tags": repeated_tags}


def get_attempt_history(session: Session, problem: Problem) -> list[Attempt]:
    return list(
        session.scalars(
            select(Attempt)
            .where(Attempt.user_id == CURRENT_USER_ID, Attempt.problem_pk == problem.id)
            .order_by(Attempt.attempt_date, Attempt.id)
        ).all()
    )


def latest_attempt(session: Session, problem: Problem) -> Attempt | None:
    history = get_attempt_history(session, problem)
    return history[-1] if history else None


def build_watch_out(session: Session, problem: Problem) -> str | None:
    history = get_attempt_history(session, problem)
    # most recent attempt that actually carries mistakes or tags
    candidates = [a for a in reversed(history) if a.mistakes or a.mistake_tags]
    if not candidates:
        return None
    attempt = candidates[0]
    parts = []
    if attempt.mistake_tags:
        parts.append(f"mistake patterns: {', '.join(attempt.mistake_tags)}")
    if attempt.mistakes:
        parts.append(f'notes: "{attempt.mistakes}"')
    if not parts:
        return None
    return (
        f"Watch out - you last attempted this on {attempt.attempt_date.isoformat()} "
        f"({','.join(parts)}). Recheck your approach covers these before submitting."
    )


def get_common_mistakes(
    session: Session, limit: int = 5, today: date | None = None
) -> dict[str, dict]:
    today = today or date.today()
    problems = {p.id: p for p in session.scalars(
        select(Problem).where(Problem.user_id == CURRENT_USER_ID)
    ).all()}
    stats: dict[str, dict] = {}
    attempts = session.scalars(
        select(Attempt).where(Attempt.user_id == CURRENT_USER_ID).order_by(Attempt.attempt_date)
    ).all()
    for attempt in attempts:
        problem = problems.get(attempt.problem_pk)
        for tag in attempt.mistake_tags or []:
            entry = stats.setdefault(
                tag, {"count": 0, "last_seen": "", "recent_problems": []}
            )
            entry["count"] += 1
            entry["last_seen"] = max(entry["last_seen"], attempt.attempt_date.isoformat())
            short = f"{problem.problem_id} ({problem.problem_description[:40]})" if problem else "?"
            if short not in entry["recent_problems"]:
                entry["recent_problems"].append(short)
    ranked = dict(
        sorted(stats.items(), key=lambda kv: (-kv[1]["count"], kv[0]))[:limit]
    )
    for entry in ranked.values():
        entry["recent_problems"] = entry["recent_problems"][-3:]
    return ranked


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    normalized = []
    for tag in tags:
        t = (tag or "").strip().lower()
        t = t if t in MISTAKE_TAGS else "other"
        if t not in normalized:
            normalized.append(t)
    return normalized


def _detect_repeated_tags(session: Session, problem: Problem, new_tags: list[str]) -> list[str]:
    if not new_tags:
        return []
    previous: set[str] = set()
    for attempt in get_attempt_history(session, problem):
        previous.update(attempt.mistake_tags or [])
    return [t for t in new_tags if t in previous]


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
