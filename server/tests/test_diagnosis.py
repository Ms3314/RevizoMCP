"""Code-diagnosis fields on attempts: diagnosis, concepts, weakness_kind.

Runs the real service functions against an in-memory sqlite DB (JSONB swapped
for portable JSON, as in test_web.py).
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import JSON, BigInteger, create_engine, inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app import database, service
from app.models import Attempt, Base, LeetCodeProblem, OAuthClient, Problem
from app.prompts import INSTRUCTIONS, SCENARIO_PLAYBOOK

TODAY = date(2026, 10, 27)


# sqlite only auto-numbers an "INTEGER PRIMARY KEY", not BIGINT
@compiles(BigInteger, "sqlite")
def _bigint_as_integer(type_, compiler, **kw):
    return "INTEGER"


@pytest.fixture()
def session():
    for model in (Problem, Attempt, LeetCodeProblem, OAuthClient):
        for col in model.__table__.columns:
            if isinstance(col.type, postgresql.JSONB):
                col.type = JSON()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        for pid in ("lc-binary-search", "lc-search-insert-position"):
            service.add_problem(s, 1, pid, "", "easy", pid, ["Binary Search"])
        yield s


def test_diagnosis_fields_are_stored_and_normalized(session):
    service.record_attempt(
        session, 1, "lc-binary-search", solved=False, mistakes="it hung",
        mistake_tags=["off_by_one"], today=TODAY,
        diagnosis="  left = mid never shrinks the window ",
        concepts=["Binary  Search Bounds", "binary search bounds", ""],
        weakness_kind="SLIP",
    )
    [attempt] = service.get_attempt_history(session, 1, service.get_problem(session, 1, "lc-binary-search"))
    assert attempt.diagnosis == "left = mid never shrinks the window"
    assert attempt.concepts == ["binary search bounds"]
    assert attempt.weakness_kind == "slip"


def test_unknown_weakness_kind_is_dropped(session):
    service.record_attempt(session, 1, "lc-binary-search", True, None, weakness_kind="maybe", today=TODAY)
    [attempt] = service.get_attempt_history(session, 1, service.get_problem(session, 1, "lc-binary-search"))
    assert attempt.weakness_kind is None
    assert attempt.concepts == []


def test_watch_out_carries_the_coach_diagnosis(session):
    service.record_attempt(
        session, 1, "lc-binary-search", False, "it hung", today=TODAY,
        diagnosis="left = mid never shrinks the window",
        concepts=["binary search bounds"], weakness_kind="gap",
    )
    watch_out = service.build_watch_out(session, 1, service.get_problem(session, 1, "lc-binary-search"))
    assert "weak concepts (gap): binary search bounds" in watch_out
    assert 'coach saw: "left = mid never shrinks the window"' in watch_out


def test_concept_repeated_on_another_problem_is_flagged(session):
    first = service.record_attempt(
        session, 1, "lc-binary-search", False, None, today=TODAY - timedelta(days=3),
        concepts=["binary search bounds"],
    )
    assert first["repeated_concepts"] == []
    second = service.record_attempt(
        session, 1, "lc-search-insert-position", False, None, today=TODAY,
        concepts=["binary search bounds", "edge: empty array"],
    )
    assert second["repeated_concepts"] == ["binary search bounds"]


def test_weak_concepts_rank_gaps_first(session):
    service.record_attempt(session, 1, "lc-binary-search", False, None, today=TODAY,
                           concepts=["sliding window shrink"], weakness_kind="slip")
    service.record_attempt(session, 1, "lc-binary-search", False, None, today=TODAY,
                           concepts=["sliding window shrink"], weakness_kind="slip")
    service.record_attempt(session, 1, "lc-search-insert-position", False, None, today=TODAY,
                           concepts=["binary search bounds"], weakness_kind="gap")
    weak = service.get_weak_concepts(session, 1)
    assert list(weak) == ["binary search bounds", "sliding window shrink"]
    assert weak["sliding window shrink"]["count"] == 2
    assert weak["binary search bounds"]["problems"] == ["lc-search-insert-position"]


def test_missing_columns_are_added_to_an_existing_table(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE attempts (id INTEGER PRIMARY KEY)"))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "ADDED_COLUMNS", {
        "attempts": {"diagnosis": "TEXT NOT NULL DEFAULT ''", "weakness_kind": "VARCHAR"},
        "not_created_yet": {"x": "TEXT"},
    })
    database._add_missing_columns()
    database._add_missing_columns()  # idempotent
    cols = {c["name"] for c in inspect(engine).get_columns("attempts")}
    assert {"diagnosis", "weakness_kind"} <= cols


def test_prompt_runs_the_diagnosis_loop():
    # code shared -> ask, don't tell -> classify slip/gap -> record structured fields
    assert "CODE DIAGNOSIS" in INSTRUCTIONS
    assert "stuck OR solved" in INSTRUCTIONS
    assert "Code diagnosis" in SCENARIO_PLAYBOOK
    assert 'weakness_kind="slip"' in SCENARIO_PLAYBOOK
    assert 'weakness_kind="gap"' in SCENARIO_PLAYBOOK
    assert "REUSE an existing concept name" in SCENARIO_PLAYBOOK
    assert "store or repeat their full code" in SCENARIO_PLAYBOOK
