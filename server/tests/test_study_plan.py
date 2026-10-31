"""Study-plan + streak API tests (Phase 5).

Exercises /api/study-plan, /api/study-plan/settings and
/api/problems/{id}/solve without a live DB: the service layer is monkeypatched
and auth is overridden via FastAPI's dependency overrides.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import service
from app.api import deps as api_deps
from app.api import routes as api_routes
from app.web.deps import UserContext
from main import app

USER = UserContext(id=1, email="tester@example.com", display_name="tester")


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def authed():
    app.dependency_overrides[api_deps.get_api_user] = lambda: USER
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def fake_session(monkeypatch):
    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(api_routes, "SessionLocal", FakeSession)


def test_study_plan_requires_auth(client):
    r = client.get("/api/study-plan")
    assert r.status_code == 401


def test_study_plan_serializes(authed, client, monkeypatch):
    sample = {
        "settings": {"revisions_per_session": 2, "backlog_per_session": 3},
        "old_target": 2,
        "old_solved_today": 1,
        "new_target": 3,
        "new_solved_today": 0,
        "old_suggestions": [],
        "new_suggestions": [],
        "weak_topics": ["edge_cases"],
        "streak": {"current": 4, "longest": 10, "days": [{"date": "2026-10-01", "count": 1}]},
    }
    monkeypatch.setattr(service, "build_study_plan", lambda *a, **k: sample)
    r = client.get("/api/study-plan")
    assert r.status_code == 200
    body = r.json()
    assert body["old_target"] == 2
    assert body["new_target"] == 3
    assert body["old_solved_today"] == 1
    assert body["streak"]["current"] == 4
    assert body["weak_topics"] == ["edge_cases"]


def test_study_plan_settings_saved(authed, client, fake_session, monkeypatch):
    captured = {}

    class FakeStrategy:
        revisions_per_session = 0
        backlog_per_session = 0

    strat = FakeStrategy()

    def fake_update(session, uid, rev, back):
        captured.update(rev=rev, back=back, uid=uid)
        strat.revisions_per_session = rev
        strat.backlog_per_session = back
        return strat

    monkeypatch.setattr(service, "update_strategy", fake_update)
    r = client.post(
        "/api/study-plan/settings",
        json={"revisions_per_session": 5, "backlog_per_session": 7},
    )
    assert r.status_code == 200
    assert captured == {"rev": 5, "back": 7, "uid": 1}
    assert r.json()["revisions_per_session"] == 5
    assert r.json()["backlog_per_session"] == 7


def test_solve_problem_returns_plan(authed, client, fake_session, monkeypatch):
    captured = {}

    def fake_record(session, uid, pid, solved, mistakes, mistake_tags):
        captured.update(uid=uid, pid=pid, solved=solved)

    monkeypatch.setattr(service, "record_attempt", fake_record)
    plan = {
        "settings": {"revisions_per_session": 1, "backlog_per_session": 1},
        "old_target": 1,
        "old_solved_today": 0,
        "new_target": 1,
        "new_solved_today": 0,
        "old_suggestions": [],
        "new_suggestions": [],
        "weak_topics": [],
        "streak": {"current": 1, "longest": 1, "days": []},
    }
    monkeypatch.setattr(service, "build_study_plan", lambda *a, **k: plan)
    r = client.post("/api/problems/Two%20Sum/solve", json={"solved": True})
    assert r.status_code == 200
    assert captured["pid"] == "Two Sum"
    assert captured["solved"] is True
    assert r.json()["old_target"] == 1
