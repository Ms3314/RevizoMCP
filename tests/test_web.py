"""Web dashboard tests.

No live database or network required: auth is handled via dependency
overrides / missing cookies, service calls are monkeypatched, and the OAuth
bridge is exercised with self-minted JWTs from app.jwtauth.
"""

import urllib.parse
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import jwtauth, service
from app.models import Problem
from app.web.deps import SESSION_COOKIE, UserContext, require_user
from main import app

CLIENT = SimpleNamespace(client_id="web_test")
USER = UserContext(id=1, email="dev@example.com", display_name="dev")


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def signed_in():
    app.dependency_overrides[require_user] = lambda: USER
    yield
    app.dependency_overrides.clear()


def _problem(**kw):
    defaults = dict(
        id=1,
        user_id=1,
        problem_id="Two Sum",
        problem_link="",
        difficulty="easy",
        problem_description="",
        last_solved=None,
        solved=False,
        topics=[],
        mistakes="",
        interval_days=0,
        repetitions=0,
    )
    defaults.update(kw)
    return Problem(**defaults)


def test_landing_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Revizo" in r.text
    assert "/connect" in r.text  # MCP setup link always present


def test_docs_all_pages_render(client):
    for slug, expected in [
        ("introduction", "About Revizo"),
        ("features", "Features"),
        ("leetcode-import", "Import your full LeetCode history"),
        ("connect", "Connect Revizo"),
        ("connect/cursor", "Add to Cursor"),
        ("connect/claude", "Add custom connector"),
        ("connect/claude-code", "claude mcp add"),
        ("connect/chatgpt", "Apps &amp; Connectors"),
        ("connect/codex", "Codex"),
        ("connect/hermes", "Hermes"),
        ("connect/other", "Streamable HTTP"),
    ]:
        r = client.get(f"/docs/{slug}")
        assert r.status_code == 200, f"/docs/{slug} failed"
        assert expected in r.text, f"/docs/{slug} missing {expected!r}"

    # the server URL box reflects the server the browser is actually on
    r = client.get("/docs/connect/cursor")
    assert "http://testserver/mcp" in r.text


def test_docs_coming_soon_pages(client):
    for slug in ("codex", "hermes"):
        r = client.get(f"/docs/connect/{slug}")
        assert "coming soon" in r.text.lower()


def test_connect_redirects_to_docs(client):
    r = client.get("/connect", follow_redirects=False)
    assert r.status_code == 308
    assert r.headers["location"] == "/docs/connect"


def test_docs_index_lists_sections(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "/docs/introduction" in r.text
    assert "/docs/connect" in r.text
    assert "/docs/leetcode-import" in r.text


def test_leetcode_settings_save_cookie_encrypted(signed_in, client, monkeypatch):
    from cryptography.fernet import Fernet

    from app import models
    import app.web.routes as routes

    cookie = "sensitive-leetcode-session-value"
    account = models.User(
        id=1, supabase_sub="sub", email="dev@example.com", display_name="dev"
    )
    monkeypatch.setenv(
        "LEETCODE_SESSION_ENCRYPTION_KEY", Fernet.generate_key().decode()
    )

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, model, user_id):
            assert model is models.User
            assert user_id == 1
            return account

        def commit(self):
            pass

    monkeypatch.setattr(routes, "SessionLocal", FakeSession)
    response = client.post(
        "/app/leetcode/settings",
        data={"username": "my-handle", "session_cookie": cookie},
    )

    assert response.status_code == 200
    assert cookie not in response.text
    assert account.leetcode_username == "my-handle"
    assert account.leetcode_session.startswith("fernet:v1:")
    assert "Connected" in response.text


def test_docs_do_not_use_the_app_shell(client):
    # docs are a separate public layout: no authenticated sidebar nav
    r = client.get("/docs/connect")
    assert 'href="/app"' not in r.text.split("</header>")[0]  # header has no dashboard link when signed out
    assert "Dashboard" not in r.text.split("<main")[1].split("</main>")[0]


def test_landing_shows_google_sign_in_when_configured(client, monkeypatch):
    monkeypatch.setattr("app.web.routes.SUPABASE_URL", "https://sup.example")
    monkeypatch.setattr("app.web.routes.SUPABASE_ANON_KEY", "anon-key")
    r = client.get("/")
    assert "Continue with Google" in r.text


def test_dashboard_redirects_anonymous(client):
    r = client.get("/app", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_starts_oauth_flow(client, monkeypatch):
    monkeypatch.setattr("app.web.routes.SUPABASE_URL", "https://sup.example")
    monkeypatch.setattr("app.web.routes.SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr("app.web.routes.ensure_web_client", lambda uris=None: CLIENT)

    r = client.get("/login", follow_redirects=False)
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith("/oauth/authorize?")
    assert "client_id=web_test" in location
    assert "code_challenge_method=S256" in location
    # regression: the round-trip must return to the origin that started login,
    # so the state cookie (host-scoped) is actually sent back
    assert f"redirect_uri={urllib.parse.quote('http://testserver/auth/callback', safe='')}" in location
    # PKCE verifier and state travel in short-lived cookies
    assert "lr_pkce" in r.cookies
    assert "lr_state" in r.cookies


def test_auth_callback_rejects_state_mismatch(client):
    r = client.get("/auth/callback?code=abc&state=wrong")
    assert r.status_code == 400
    assert "state mismatch" in r.text


def test_auth_callback_mints_session(client, monkeypatch):
    monkeypatch.setattr("app.web.routes.ensure_web_client", lambda uris=None: CLIENT)
    state = "st_123"
    code = jwtauth.mint_auth_code(
        sub="1", client_id="web_test", redirect_uri="http://x/auth/callback", code_challenge="c"
    )
    client.cookies.set("lr_state", state)  # emulate the cookie set by /login
    r = client.get(
        f"/auth/callback?code={urllib.parse.quote(code)}&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/app"
    assert SESSION_COOKIE in r.cookies
    claims = jwtauth.verify_access_token(r.cookies[SESSION_COOKIE])
    assert claims["sub"] == "1"


def test_dashboard_renders_stats_and_timeline(signed_in, monkeypatch, client):
    problems = [
        _problem(),
        _problem(
            id=2,
            problem_id="Coin Change",
            difficulty="hard",
            solved=True,
            topics=["dp"],
            last_solved=date(2026, 9, 20),
            interval_days=7,
            repetitions=2,
        ),
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
        "watch_outs": {problems[0].id: "you did an off-by-one here"},
        "weak": {},
        "history": {p.id: [] for p in problems},
    }
    monkeypatch.setattr(
        service,
        "dashboard_data",
        lambda s, uid, today=None, due_limit=10, weak_limit=5: data,
    )

    r = client.get("/app")
    assert r.status_code == 200
    assert "Two Sum" in r.text
    assert "Coin Change" in r.text
    assert "Due today" in r.text
    assert "off-by-one" in r.text  # due-today watch-out
    assert "Weak points" in r.text


def test_dashboard_data_matches_per_page_helpers():
    # dashboard_data must agree with the per-page service helpers it replaced
    # (same stats, due ranking, watch-outs, weak points, history) — computed on
    # an in-memory sqlite DB so the comparison is self-contained.
    from datetime import timedelta

    from sqlalchemy import JSON, create_engine
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import sessionmaker

    from app import srs
    from app.database import Base
    from app.models import Attempt, LeetCodeProblem, OAuthClient, Problem, User

    # JSONB is postgres-only; swap to portable JSON before any DDL is emitted
    for model in (Problem, Attempt, LeetCodeProblem, OAuthClient):
        for col in model.__table__.columns:
            if isinstance(col.type, postgresql.JSONB):
                col.type = JSON()

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    today = date(2026, 9, 28)
    with Session() as session:
        session.add(User(id=1, supabase_sub="sub", email="a@b.c", display_name="a"))
        p1 = _problem(id=10, problem_id="Inversions", difficulty="hard", solved=True,
                      last_solved=today - timedelta(days=9), interval_days=3, repetitions=1,
                      problem_description="count inversions", topics=["arrays"])
        p2 = _problem(id=11, problem_id="Two Sum", difficulty="easy", solved=False,
                      last_solved=None, interval_days=0, repetitions=0, topics=["hashing"])
        session.add_all([p1, p2])
        session.add(Attempt(id=100, user_id=1, problem_pk=10, attempt_date=today - timedelta(days=9),
                            solved=False, mistakes="tle", mistake_tags=["complexity_tle"]))
        session.add(Attempt(id=101, user_id=1, problem_pk=10, attempt_date=today - timedelta(days=2),
                            solved=True, mistakes="", mistake_tags=[]))
        session.commit()

        fast = service.dashboard_data(session, user_id=1, today=today)

        assert fast["stats"] == service.revision_stats(session, user_id=1, today=today)
        assert [p.id for p in fast["due_problems"]] == [
            p.id for p in service.get_due_problems(session, user_id=1, today=today)
        ]
        assert fast["watch_outs"] == {
            p.id: service.build_watch_out(session, 1, p) for p in fast["due_problems"]
        }
        assert fast["weak"] == service.get_common_mistakes(session, user_id=1, limit=5, today=today)
        for p in fast["problems"]:
            assert fast["history"][p.id] == service.get_attempt_history(session, 1, p)
        assert fast["problems"] == service.list_all_problems(session, user_id=1)
        assert srs.is_due(p1.last_solved, p1.interval_days, p1.solved, today)  # sanity


def test_add_problem_duplicate_shows_inline_error(signed_in, monkeypatch, client):
    def duplicate(session, user_id, **kw):
        raise ValueError("Problem 'Two Sum' already exists")

    monkeypatch.setattr(service, "add_problem", duplicate)
    r = client.post(
        "/app/problems/new",
        data={"title": "Two Sum", "difficulty": "easy", "topics": "", "link": "", "description": ""},
    )
    assert r.status_code == 400
    assert "already exists" in r.text


def test_add_problem_success_redirects(signed_in, monkeypatch, client):
    calls = {}

    def fake_add(session, user_id, **kw):
        calls.update(kw)

    monkeypatch.setattr(service, "add_problem", fake_add)
    r = client.post(
        "/app/problems/new",
        data={
            "title": "Longest Consecutive Sequence",
            "difficulty": "medium",
            "topics": "arrays, hashing",
            "link": "https://leetcode.com/problems/longest-consecutive-sequence/",
            "description": "",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/app"
    assert calls["problem_id"] == "Longest Consecutive Sequence"
    assert calls["topics"] == ["arrays", "hashing"]


def test_add_problem_requires_title(signed_in, client):
    r = client.post("/app/problems/new", data={"title": "  "})
    assert r.status_code == 400
    assert "title" in r.text.lower()
