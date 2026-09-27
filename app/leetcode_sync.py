import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
GRAPHQL_PACE_SECONDS = 0.4

ACCEPTED = "Accepted"

# Loose mapping from public LeetCode statuses to the tracker's mistake-tag
# vocabulary. Only statuses that are unambiguous on their own get a tag;
# anything else records NO tag (we never fabricate a diagnosis).
FAILURE_TAG_MAP: dict[str, str] = {
    "Time Limit Exceeded": "complexity_tle",
    "Runtime Error": "implementation_bug",
}

_question_cache: dict[str, dict] | None = None


def failure_tag_for(status_display: str) -> str | None:
    """Mistake tag for a non-accepted status; None when it cannot be inferred."""
    return FAILURE_TAG_MAP.get(status_display)


def group_window_by_slug(recent: list[dict]) -> dict[str, list[dict]]:
    """Group the all-status submission window (newest-first) by problem slug.

    Pure function - the newest entry per slug decides the tracked state of the
    problem (Accepted -> solved, anything else -> unsolved/stuck).
    """
    by_slug: dict[str, list[dict]] = {}
    for entry in recent:  # window arrives newest-first
        by_slug.setdefault(entry["slug"], []).append(entry)
    return by_slug


def _graphql(query: str, variables: dict | None = None) -> dict:
    """POST a GraphQL query to LeetCode's public endpoint (no authentication)."""
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    headers = {
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
        "Origin": "https://leetcode.com",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ),
    }
    req = urllib.request.Request(LEETCODE_GRAPHQL_URL, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"LeetCode API returned HTTP {e.code}: {e.reason}") from e
    if "errors" in body:
        raise RuntimeError(f"LeetCode GraphQL error: {body['errors']}")
    return body["data"]


def _load_question_catalog() -> dict[str, dict]:
    """One-time bulk fetch of all LeetCode questions: slug -> {title, difficulty, topics}."""
    global _question_cache
    if _question_cache is not None:
        return _question_cache

    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList: questionList(categorySlug: $categorySlug, limit: $limit, skip: $skip, filters: $filters) {
        total: totalNum
        questions: data {
          title
          titleSlug
          difficulty
          topicTags { name }
        }
      }
    }
    """
    catalog: dict[str, dict] = {}
    skip = 0
    page_size = 100
    total = None
    while True:
        data = _graphql(
            query,
            {"categorySlug": "", "limit": page_size, "skip": skip, "filters": {}},
        )
        page = data["problemsetQuestionList"]
        total = page["total"]
        for q in page["questions"] or []:
            catalog[q["titleSlug"]] = {
                "title": q["title"],
                "difficulty": (q["difficulty"] or "Medium").lower(),
                "topics": [t["name"] for t in q["topicTags"] or []],
            }
        skip += page_size
        if total is None or skip >= total or not page["questions"]:
            break
        time.sleep(GRAPHQL_PACE_SECONDS)

    _question_cache = catalog
    return catalog


def fetch_recent_acs(username: str, limit: int = 200) -> list[dict]:
    query = """
    query recentAcSubmissions($username: String!, $limit: Int!) {
      recentAcSubmissionList(username: $username, limit: $limit) {
        id
        title
        titleSlug
        timestamp
      }
    }
    """
    data = _graphql(query, {"username": username, "limit": limit})
    submissions = data["recentAcSubmissionList"] or []
    return [
        {
            "submission_id": str(s["id"]),
            "title": s["title"],
            "slug": s["titleSlug"],
            "ac_utc": datetime.fromtimestamp(int(s["timestamp"]), timezone.utc).isoformat() if s.get("timestamp") else None,
        }
        for s in submissions
    ]


def fetch_recent_submissions(username: str, limit: int = 20) -> list[dict]:
    """The user's last `limit` submissions of ANY status (public profile data).

    Each entry: submission_id, title, slug, status_display (Accepted / Wrong
    Answer / Time Limit Exceeded / Runtime Error ...), lang, utc. Source code is
    NOT available here - submission code is private to the authenticated user.
    """
    query = """
    query recentSubmissions($username: String!, $limit: Int!) {
      recentSubmissionList(username: $username, limit: $limit) {
        id
        title
        titleSlug
        timestamp
        statusDisplay
        lang
      }
    }
    """
    data = _graphql(query, {"username": username, "limit": limit})
    submissions = data["recentSubmissionList"] or []
    return [
        {
            "submission_id": str(s["id"]),
            "title": s["title"],
            "slug": s["titleSlug"],
            "status_display": s.get("statusDisplay") or "Unknown",
            "lang": s.get("lang"),
            "utc": (
                datetime.fromtimestamp(int(s["timestamp"]), timezone.utc).isoformat()
                if s.get("timestamp")
                else None
            ),
        }
        for s in submissions
    ]


def _entry_date(entry: dict) -> date:
    """UTC calendar date of a submission entry; today as a defensive fallback."""
    raw = entry.get("utc") or entry.get("ac_utc")
    return datetime.fromisoformat(raw).date() if raw else date.today()


def sync_recent(
    limit: int = 50, username: str | None = None, user_id: int | None = None
) -> dict:
    """Import recent LeetCode activity from PUBLIC endpoints only. Idempotent per submission.

    - Accepted submissions become solved problems on rung 1 of their difficulty
      ladder, with attempt_date set to the real AC date.
    - Recent FAILED submissions (the last ~20 submissions of any status) become
      unsolved backlog problems carrying attempt-history rows, so the tracker
      learns what the user is stuck on.

    Known blind spot (public-API limitation): a problem solved BEFORE the
    ~20-submission window but failed INSIDE it imports as unsolved. Accepted
    noise; syncs are never destructive - submissions dedup by their unique ids.

    username is mandatory unless the account already has one on file (the
    caller passes the stored one). user_id must be the authenticated user's id.
    """
    username = (username or "").strip()
    if not username:
        raise RuntimeError(
            "A LeetCode username is required — ask the user for their LeetCode ID "
            "(their public profile handle) before calling sync_leetcode"
        )
    if user_id is None:
        raise RuntimeError("user_id is required (the authenticated user's id)")

    from app import service
    from app import srs
    from app.database import SessionLocal
    from app.models import Attempt, Problem

    acs = fetch_recent_acs(username, limit)
    recent = fetch_recent_submissions(username, limit=20)

    added = skipped = failed_imported = 0
    with SessionLocal() as session:
        existing = {
            p.problem_id
            for p in session.scalars(
                select(Problem).where(Problem.user_id == user_id)
            ).all()
        }
        # Submission-level dedup in ONE batched query. LeetCode submission ids are
        # globally unique, so no user filter is needed here.
        all_ids = [a["submission_id"] for a in acs] + [
            r["submission_id"] for r in recent
        ]
        stored: set[str] = (
            set(
                session.scalars(
                    select(Attempt.lc_submission_id).where(
                        Attempt.lc_submission_id.in_(all_ids)
                    )
                ).all()
            )
            if all_ids
            else set()
        )

        # Walk the all-status window newest -> oldest, keeping only not-yet-stored
        # submissions. The first stored id marks the imported border: everything
        # older than it was recorded by an earlier sync (invariant: every sync
        # records the id of EVERY submission it processes, and commits atomically
        # once at the end - so there is never a half-stamped border). With the
        # ~20-item public window this is a micro-optimisation; it pays off if a
        # full-history (cookie) sync ever returns.
        fresh: list[dict] = []
        for entry in recent:  # already newest-first
            if entry["submission_id"] in stored:
                break
            fresh.append(entry)

        by_slug = group_window_by_slug(fresh)
        window_slugs = set(by_slug)

        # 1) Older ACs still in the accepted feed but outside the all-status
        #    window: the classic solved-problem import (unchanged behaviour).
        for ac in acs:
            slug = ac["slug"]
            if slug in window_slugs:
                continue  # handled by the window path below
            problem_id = f"lc-{slug}"
            if problem_id in existing:
                skipped += 1
                continue

            question = _load_question_catalog().get(slug, {})
            problem = service.add_problem(
                session,
                user_id=user_id,
                problem_id=problem_id,
                problem_link=f"https://leetcode.com/problems/{slug}/",
                difficulty=question.get("difficulty", "medium"),
                problem_description=question.get("title") or ac["title"],
                topics=question.get("topics", []),
            )
            ac_date = _entry_date(ac)
            problem.solved = True
            problem.last_solved = ac_date
            problem.repetitions = 1
            problem.interval_days = srs.ladder_for(problem.difficulty)[0]

            session.add(
                Attempt(
                    user_id=user_id,
                    problem_pk=problem.id,
                    attempt_date=ac_date,
                    solved=True,
                    mistakes="",
                    mistake_tags=[],
                    lc_submission_id=ac["submission_id"],
                )
            )
            existing.add(problem_id)
            added += 1

        # 2) The all-status window: fresh submissions grouped by problem. The
        #    newest submission per slug decides the tracked state.
        for slug, entries in by_slug.items():
            problem_id = f"lc-{slug}"
            newest = entries[0]  # newest-first
            solved_now = newest["status_display"] == ACCEPTED

            problem = None
            if problem_id in existing:
                skipped += 1
                problem = session.scalars(
                    select(Problem).where(
                        Problem.user_id == user_id, Problem.problem_id == problem_id
                    )
                ).first()
            else:
                question = _load_question_catalog().get(slug, {})
                problem = service.add_problem(
                    session,
                    user_id=user_id,
                    problem_id=problem_id,
                    problem_link=f"https://leetcode.com/problems/{slug}/",
                    difficulty=question.get("difficulty", "medium"),
                    problem_description=question.get("title") or newest["title"],
                    topics=question.get("topics", []),
                )
                existing.add(problem_id)
                added += 1
                if solved_now:
                    # Fresh solve (possibly after WAs inside the window): the
                    # replay ends on a solve, i.e. repetitions 0 -> 1 on rung 1.
                    problem.solved = True
                    problem.last_solved = _entry_date(newest)
                    problem.repetitions = 1
                    problem.interval_days = srs.ladder_for(problem.difficulty)[0]

            # Self-heal: an unsolved (failed) import whose newest window
            # submission is now Accepted - the user cracked it since. Mirrors
            # record_attempt's solve path. We deliberately never auto-FAIL a
            # tracked problem from sync: if the newest submission is a failure
            # we only record the attempt row and let the coach handle it in
            # conversation.
            if solved_now and problem is not None and not problem.solved:
                problem.solved = True
                problem.last_solved = _entry_date(newest)
                problem.interval_days = srs.next_interval(
                    problem.difficulty, problem.repetitions, True
                )
                problem.repetitions += 1

            # Attempt history: oldest -> newest so the diary reads chronologically.
            for entry in reversed(entries):
                if entry["submission_id"] in stored:
                    continue  # paranoia; the fresh walk already excluded these
                solved_i = entry["status_display"] == ACCEPTED
                if solved_i:
                    mistakes_text, tags = "", []
                else:
                    failed_imported += 1
                    mistakes_text = f"LeetCode sync: {entry['status_display']}"
                    tag = failure_tag_for(entry["status_display"])
                    tags = [tag] if tag else []
                session.add(
                    Attempt(
                        user_id=user_id,
                        problem_pk=problem.id,
                        attempt_date=_entry_date(entry),
                        solved=solved_i,
                        mistakes=mistakes_text,
                        mistake_tags=tags,
                        lc_submission_id=entry["submission_id"],
                    )
                )

        session.commit()

    return {
        "username": username,
        "fetched": len(acs) + len(recent),
        "added": added,
        "failed_imported": failed_imported,
        "skipped_existing": skipped,
    }
