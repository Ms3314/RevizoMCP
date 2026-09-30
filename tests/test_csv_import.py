"""CSV import tests: parsing logic + the web upload flow.

No live database needed — service calls are monkeypatched, auth via
dependency overrides, matching the conventions in test_web.py.
"""

import json

import pytest

from app.web.csv_import import Skip, parse_csv


def _csv(*rows: str) -> str:
    return "\n".join(rows) + "\n"


def test_basic_import_extracts_canonical_fields():
    text = _csv(
        "Problem,Link,Difficulty,Topics,Description",
        'Two Sum,https://leetcode.com/problems/two-sum/,easy,"arrays, hashing",Find two numbers.',
        "Coin Change,https://leetcode.com/problems/coin-change/,medium,dp,",
    )
    parsed = parse_csv(text)
    assert len(parsed.rows) == 2
    assert parsed.skipped == []
    assert parsed.rows[0] == {
        "title": "Two Sum",
        "link": "https://leetcode.com/problems/two-sum/",
        "difficulty": "easy",
        "topics": ["arrays", "hashing"],
        "description": "Find two numbers.",
    }
    assert parsed.rows[1]["topics"] == ["dp"]
    assert parsed.rows[1]["difficulty"] == "medium"


def test_synonym_and_case_insensitive_headers():
    text = _csv(
        "NAME , Problem URL , Level , Tag , Notes",
        "Two Sum,https://x.com/ts,Hard,arrays,some notes",
    )
    parsed = parse_csv(text)
    assert len(parsed.rows) == 1
    row = parsed.rows[0]
    assert row["title"] == "Two Sum"
    assert row["link"] == "https://x.com/ts"
    assert row["difficulty"] == "hard"
    assert row["topics"] == ["arrays"]
    assert row["description"] == "some notes"


def test_extra_columns_and_rows_are_ignored():
    text = _csv(
        "Problem,Link,Starred,Sub-step,Last revised",
        "Two Sum,https://x.com/ts,Yes,Stuff,2024-01-01",
    )
    parsed = parse_csv(text)
    assert len(parsed.rows) == 1
    assert "Starred" in parsed.extras_ignored
    assert "Sub-step" in parsed.extras_ignored
    assert "Last revised" in parsed.extras_ignored
    assert parsed.rows[0]["title"] == "Two Sum"


def test_rows_missing_title_or_link_are_skipped_with_row_number():
    text = _csv(
        "Problem,Link",
        "No Link Here,",
        ",https://x.com/orphan",
        "Good,https://x.com/good",
    )
    parsed = parse_csv(text)
    assert [r["title"] for r in parsed.rows] == ["Good"]
    assert parsed.skipped == [Skip(1, "missing link"), Skip(2, "missing title")]


def test_blank_rows_are_not_reported_as_skipped():
    text = _csv(
        "Problem,Link",
        "",
        "Two Sum,https://x.com/ts",
        ",",
    )
    parsed = parse_csv(text)
    assert len(parsed.rows) == 1
    assert parsed.skipped == []


def test_unknown_difficulty_defaults_to_medium():
    text = _csv(
        "Problem,Link,Difficulty",
        "Weird,https://x.com/w,impossible",
        "Blank,https://x.com/b,",
    )
    parsed = parse_csv(text)
    assert [r["difficulty"] for r in parsed.rows] == ["medium", "medium"]


def test_no_required_columns_raises_helpful_error():
    with pytest.raises(ValueError, match="required columns"):
        parse_csv("Foo,Bar\n1,2\n")


def test_empty_file_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_csv("")


def test_first_column_mapping_wins_on_duplicate_match():
    # two different headers both mapping to "title" -> first one wins, second ignored
    text = _csv(
        "Problem,Title,Link",
        "Real,Other,https://x.com/ts",
    )
    parsed = parse_csv(text)
    assert parsed.rows[0]["title"] == "Real"


# ------------------------------------------------------------------ web route


@pytest.fixture()
def web_client():
    from fastapi.testclient import TestClient

    from app.web.deps import require_user
    from main import app
    from tests.test_web import USER

    app.dependency_overrides[require_user] = lambda: USER
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def fake_db(monkeypatch):
    """Replace routes.SessionLocal with a no-op session and capture service calls."""
    added = []

    def _add(session, user_id, **kw):
        added.append((user_id, kw))
        if kw["problem_id"].startswith("Dup"):
            raise ValueError("already exists")

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def commit(self):
            pass

        def close(self):
            pass

    from app.web import routes

    monkeypatch.setattr(routes, "SessionLocal", _FakeSession)
    monkeypatch.setattr(routes.service, "add_problem", _add)
    return added


def test_import_page_renders_when_signed_in(web_client):
    r = web_client.get("/app/import")
    assert r.status_code == 200
    assert "Import problems" in r.text


def test_import_rejects_non_csv(web_client):
    r = web_client.post(
        "/app/import", files={"file": ("problems.txt", b"hello", "text/plain")}
    )
    assert r.status_code == 400
    assert "Only .csv" in r.text


def test_import_end_to_end_summary(web_client, fake_db):
    csv = _csv(
        "Problem,Link",
        "Two Sum,https://x.com/ts",
        "Dup Thing,https://x.com/dup",
        "Missing Link,",
        ",https://x.com/orphan",
    )
    r = web_client.post(
        "/app/import", files={"file": ("problems.csv", csv.encode(), "text/csv")}
    )
    assert r.status_code == 200
    # Parse SSE events
    events = []
    for line in r.text.split('\n'):
        if line.startswith('data: '):
            events.append(json.loads(line[6:]))
    
    assert any(e['type'] == 'start' for e in events)
    progress_events = [e for e in events if e['type'] == 'progress']
    assert len(progress_events) > 0
    done_event = [e for e in events if e['type'] == 'done'][0]
    
    assert done_event['imported'] == 1  # only "Two Sum" (Dup Thing is duplicate)
    assert done_event['duplicates'] == 1
    assert len(done_event['skipped']) == 2  # missing link + missing title
    # only the non-duplicate, non-skipped rows reached the service layer
    assert [kw["problem_id"] for _, kw in fake_db] == ["Two Sum", "Dup Thing"]
    assert all(user_id == 1 for user_id, _ in fake_db)


def test_import_reports_no_importable_rows(web_client, fake_db):
    csv = _csv("Problem,Link\n,https://x.com/orphan\n")
    r = web_client.post(
        "/app/import", files={"file": ("problems.csv", csv.encode(), "text/csv")}
    )
    assert r.status_code == 400
    assert "No importable problems" in r.text
