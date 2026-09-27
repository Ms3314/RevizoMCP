"""Unit tests for the public-only LeetCode sync helpers (no network, no DB)."""

from app.leetcode_sync import (
    ACCEPTED,
    failure_tag_for,
    group_window_by_slug,
)


def _sub(sid: int, slug: str, status: str) -> dict:
    return {
        "submission_id": str(sid),
        "title": "Title",
        "slug": slug,
        "status_display": status,
        "lang": "python3",
        "utc": "2026-09-20T10:00:00+00:00",
    }


def test_groups_by_slug_newest_first():
    window = [
        _sub(3, "two-sum", "Wrong Answer"),
        _sub(2, "two-sum", ACCEPTED),
        _sub(1, "count-inversions", "Time Limit Exceeded"),
    ]
    grouped = group_window_by_slug(window)

    assert list(grouped) == ["two-sum", "count-inversions"]
    assert [e["submission_id"] for e in grouped["two-sum"]] == ["3", "2"]
    # newest status decides the problem state
    assert grouped["two-sum"][0]["status_display"] != ACCEPTED
    assert grouped["count-inversions"][0]["status_display"] != ACCEPTED


def test_solved_after_wa_reads_as_solved():
    window = [
        _sub(9, "valid-parentheses", ACCEPTED),
        _sub(8, "valid-parentheses", "Wrong Answer"),
        _sub(7, "valid-parentheses", "Runtime Error"),
    ]
    grouped = group_window_by_slug(window)
    entries = grouped["valid-parentheses"]

    assert entries[0]["status_display"] == ACCEPTED  # replay ends on a solve
    assert [e["submission_id"] for e in reversed(entries)] == ["7", "8", "9"]


def test_single_entry_slugs():
    grouped = group_window_by_slug([_sub(5, "coin-change", "Wrong Answer")])
    assert grouped["coin-change"][0]["submission_id"] == "5"


def test_failure_tag_mapping():
    assert failure_tag_for("Time Limit Exceeded") == "complexity_tle"
    assert failure_tag_for("Runtime Error") == "implementation_bug"
    assert failure_tag_for("Wrong Answer") is None  # never fabricate a diagnosis
    assert failure_tag_for(ACCEPTED) is None
