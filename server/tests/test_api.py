"""JSON API tests (Phase 1).

Exercises /api/me, /api/dashboard and /api/problems without a live DB: the
service layer is monkeypatched and auth is overridden via FastAPI's dependency
overrides (the SPA's 401 path is checked separately).
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import service
from app.api import deps as api_deps
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


def test_me_requires_auth(client):
    r = client.get("/api/me")
    assert r.status_code == 401


def test_me_returns_user(authed, client):
    r = client.get("/api/me")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == USER.id
    assert body["email"] == USER.email


def test_dashboard_serializes(authed, client, monkeypatch):
    problems = [
        _p(1, "Two Sum", "easy", solved=False, topics=["arrays"]),
        _p(2, "Coin Change", "hard", solved=True, topics=["dp"], last_solved=date(2026, 9, 20)),
    ]
    data = {
        "problems": problems,
        "stats": {
            "total": 2,
            "solved": 1,
            "backlog": 1,
            "due_today": 1,
            "by_difficulty": {"easy": 1, "medium": 0, "hard": 1},
        },
        "due_problems": [problems[0]],
        "watch_outs": {problems[0].id: "watch this"},
        "weak": {
            "edge_cases": {
                "count": 3,
                "last_seen": "2026-09-01",
                "recent_problems": ["Two Sum (…)"],
            }
        },
        "history": {p.id: [] for p in problems},
    }
    monkeypatch.setattr(service, "dashboard_data", lambda *a, **k: data)

    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["total"] == 2
    assert body["rows"][0]["p"]["problem_id"] == "Two Sum"
    assert body["due"][0]["when"] == "never attempted"
    assert body["weak_points"][0]["pct"] == 100
    # filter query params still flow through
    r2 = client.get("/api/dashboard?difficulty=hard")
    assert r2.status_code == 200
    assert r2.json()["filters"]["difficulty"] == "hard"
    assert len(r2.json()["rows"]) == 1


def test_add_problem_calls_service(authed, client, monkeypatch):
    captured = {}

    def fake_add(session, uid, problem_id, problem_link, difficulty, problem_description, topics):
        captured.update(
            uid=uid,
            problem_id=problem_id,
            problem_link=problem_link,
            difficulty=difficulty,
            problem_description=problem_description,
            topics=topics,
        )
        return None

    monkeypatch.setattr(service, "add_problem", fake_add)
    r = client.post(
        "/api/problems",
        json={"title": "Two Sum", "link": "https://x/ts", "difficulty": "easy", "topics": "arrays, hashing"},
    )
    assert r.status_code == 200
    assert captured["problem_id"] == "Two Sum"
    assert captured["topics"] == ["arrays", "hashing"]


def test_add_problem_rejects_empty_title(authed, client):
    r = client.post("/api/problems", json={"title": "   "})
    assert r.status_code == 400


def _p(id, problem_id, difficulty, solved, topics, last_solved=None):
    from app.models import Problem

    return Problem(
        id=id,
        user_id=1,
        problem_id=problem_id,
        problem_link="",
        difficulty=difficulty,
        problem_description="",
        last_solved=last_solved,
        solved=solved,
        topics=topics,
        mistakes="",
        interval_days=0,
        repetitions=0,
    )
