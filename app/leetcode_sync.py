import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"
GRAPHQL_PACE_SECONDS = 0.4

_question_cache: dict[str, dict] | None = None


def _graphql(
    query: str, variables: dict | None = None, session_cookie: str | None = None
) -> dict:
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
    cookie = (session_cookie or "").strip()
    if cookie:
        headers["Cookie"] = f"LEETCODE_SESSION={cookie}"
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
            "title": s["title"],
            "slug": s["titleSlug"],
            "ac_utc": datetime.fromtimestamp(int(s["timestamp"]), timezone.utc).isoformat() if s.get("timestamp") else None,
        }
        for s in submissions
    ]


def sync_recent_ac(
    limit: int = 50, username: str | None = None, user_id: int | None = None
) -> dict:
    """Import recent accepted submissions as solved problems. Idempotent.

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

    recent = fetch_recent_acs(username, limit)

    added = 0
    skipped = 0
    with SessionLocal() as session:
        existing = {
            p.problem_id
            for p in session.scalars(
                select(Problem).where(Problem.user_id == user_id)
            ).all()
        }
        for ac in recent:
            problem_id = f"lc-{ac['slug']}"
            if problem_id in existing:
                skipped += 1
                continue

            question = _load_question_catalog().get(ac["slug"], {})
            difficulty = question.get("difficulty", "medium")
            topics = question.get("topics", [])
            ac_date = (
                datetime.fromisoformat(ac["ac_utc"]).date() if ac["ac_utc"] else None
            )

            problem = service.add_problem(
                session,
                user_id=user_id,
                problem_id=problem_id,
                problem_link=f"https://leetcode.com/problems/{ac['slug']}/",
                difficulty=difficulty,
                problem_description=question.get("title") or ac["title"],
                topics=topics,
            )
            problem.solved = True
            problem.last_solved = ac_date
            problem.repetitions = 1
            problem.interval_days = srs.ladder_for(difficulty)[0]

            session.add(
                Attempt(
                    user_id=user_id,
                    problem_pk=problem.id,
                    attempt_date=ac_date,
                    solved=True,
                    mistakes="",
                    mistake_tags=[],
                )
            )
            existing.add(problem_id)
            added += 1
        session.commit()

    return {
        "username": username,
        "fetched": len(recent),
        "added": added,
        "skipped_existing": skipped,
    }


def fetch_submissions(
    slug: str, limit: int = 10, with_code: bool = True, session_cookie: str | None = None
) -> list[dict]:
    """Fetch the caller's own submission history for one question (private data)."""
    session_cookie = (session_cookie or "").strip()
    if not session_cookie:
        raise RuntimeError(
            "LeetCode submissions are private to their owner. Add your LEETCODE_SESSION "
            "cookie on the connect page to enable this tool."
        )
    query = """
    query recentSubmissions($questionSlug: String!, $limit: Int!) {
      submissionList(questionSlug: $questionSlug, limit: $limit) {
        submissions {
          id
          statusDisplay
          lang
          runtime
          timestamp
        }
      }
    }
    """
    data = _graphql(query, {"questionSlug": slug, "limit": limit}, session_cookie=session_cookie)
    submission_list = data["submissionList"] or {}
    submissions = submission_list.get("submissions") or []

    results = []
    for i, s in enumerate(submissions):
        entry = {
            "submission_id": s["id"],
            "status": s["statusDisplay"],
            "language": s.get("lang"),
            "runtime": s.get("runtime"),
            "utc_time": datetime.fromtimestamp(int(s["timestamp"]), timezone.utc).isoformat() if s.get("timestamp") else None,
        }
        if with_code and i < 5:
            detail = _graphql(
                "query($id: ID!) { submissionDetail(submissionId: $id) { code runtime error } }",
                {"id": s["id"]},
            )["submissionDetail"]
            code = detail.get("code") or ""
            entry["code"] = code[:6000] if code else ""
        results.append(entry)
    return results
