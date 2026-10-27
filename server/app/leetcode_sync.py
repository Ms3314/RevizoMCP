import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from http.cookies import SimpleCookie

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
_csrf_cache: dict[str, str] = {}


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


def _graphql(
    query: str, variables: dict | None = None, session_cookie: str | None = None
) -> dict:
    """POST a LeetCode GraphQL query, optionally using a signed-in session."""
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
    if session_cookie:
        headers["Cookie"] = f"LEETCODE_SESSION={session_cookie}"
        csrf = _csrf_token(session_cookie)
        if csrf:
            headers["Cookie"] += f"; csrftoken={csrf}"
            headers["x-csrftoken"] = csrf
    req = urllib.request.Request(LEETCODE_GRAPHQL_URL, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"LeetCode API returned HTTP {e.code}: {e.reason}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError("Could not reach LeetCode. Try the import again shortly.") from e
    if "errors" in body:
        raise RuntimeError(f"LeetCode GraphQL error: {body['errors']}")
    return body["data"]


def _csrf_token(session_cookie: str) -> str:
    """LeetCode's GraphQL POST expects the CSRF cookie/header pair."""
    cache_key = hashlib.sha256(session_cookie.encode()).hexdigest()
    if cache_key in _csrf_cache:
        return _csrf_cache[cache_key]
    req = urllib.request.Request(
        "https://leetcode.com/",
        headers={
            "Cookie": f"LEETCODE_SESSION={session_cookie}",
            "User-Agent": "Mozilla/5.0 (compatible; Revizo/1.0)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            for set_cookie in resp.headers.get_all("Set-Cookie", []):
                cookies = SimpleCookie()
                cookies.load(set_cookie)
                morsel = cookies.get("csrftoken")
                if morsel:
                    _csrf_cache[cache_key] = morsel.value
                    return morsel.value
    except (urllib.error.URLError, TimeoutError):
        return ""
    _csrf_cache[cache_key] = ""
    return ""


def normalize_session_cookie(value: str) -> str:
    """Accept either the cookie value or a copied ``LEETCODE_SESSION=value``."""
    value = (value or "").strip().strip('"').strip("'")
    if value.lower().startswith("leetcode_session="):
        value = value.split("=", 1)[1].strip()
    if not value or any(char in value for char in "\r\n;"):
        raise ValueError("Enter the LEETCODE_SESSION cookie value only.")
    return value


def is_encrypted_session_cookie(value: str) -> bool:
    return bool(value and value.startswith("fernet:v1:"))


def fetch_solved_count(username: str, session_cookie: str) -> int:
    """Read LeetCode's per-difficulty unique solved counts for this account."""
    query = """
    query userQuestionProgress($userSlug: String!) {
      userStatus { isSignedIn username }
      userProfileUserQuestionProgressV2(userSlug: $userSlug) {
        numAcceptedQuestions { difficulty count }
      }
    }
    """
    data = _graphql(query, {"userSlug": username}, session_cookie=session_cookie)
    status = data.get("userStatus") or {}
    if not status.get("isSignedIn"):
        raise RuntimeError("LeetCode session is not valid. Replace it in LeetCode settings.")
    authenticated_username = (status.get("username") or "").strip()
    if authenticated_username and authenticated_username.casefold() != username.casefold():
        raise RuntimeError(
            f"The saved LeetCode session belongs to '{authenticated_username}', not '{username}'. "
            "Update the username in LeetCode settings."
        )
    progress = data.get("userProfileUserQuestionProgressV2") or {}
    counts = progress.get("numAcceptedQuestions") or []
    all_count = next(
        (int(item.get("count") or 0) for item in counts if (item.get("difficulty") or "").casefold() == "all"),
        None,
    )
    return all_count if all_count is not None else sum(
        int(item.get("count") or 0)
        for item in counts
        if (item.get("difficulty") or "").casefold() != "all"
    )


def fetch_solved_questions(session_cookie: str) -> dict[str, dict]:
    """Read the signed-in user's complete solved-slug set from LeetCode."""
    query = """
    query allQuestions {
      allQuestions {
        title
        titleSlug
        status
        difficulty
        topicTags { name }
      }
    }
    """
    data = _graphql(query, session_cookie=session_cookie)
    solved: dict[str, dict] = {}
    for item in data.get("allQuestions") or []:
        slug = item.get("titleSlug")
        if not slug or (item.get("status") or "").casefold() not in {"ac", "accepted"}:
            continue
        solved[slug] = {
            "title": item.get("title") or slug,
            "difficulty": (item.get("difficulty") or "Medium").lower(),
            "topics": [tag["name"] for tag in item.get("topicTags") or [] if tag.get("name")],
        }
    return solved


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


def import_all_solved(
    *, username: str, session_cookie: str, user_id: int
) -> dict:
    """Import all solved LeetCode problems, then only newly solved problems later.

    The profile's unique solved count avoids another question-list request when
    nothing has changed. When it increases, an authenticated `allQuestions`
    query returns solved slugs; the per-user import table determines which are
    genuinely new. Tracked problems and sync state are committed atomically.
    """
    username = (username or "").strip()
    session_cookie = normalize_session_cookie(session_cookie)
    if not username:
        raise RuntimeError("A LeetCode username is required. Add it in LeetCode settings.")
    if user_id is None:
        raise RuntimeError("user_id is required (the authenticated user's id)")

    from app import service, srs
    from app.database import SessionLocal
    from app.models import (
        LeetCodeProblem,
        LeetCodeSyncState,
        Problem,
        User,
    )

    solved_count = fetch_solved_count(username, session_cookie)
    with SessionLocal() as session:
        state = session.get(LeetCodeSyncState, user_id)
        previous_count = state.solved_count if state else None
        previous_username = state.username if state else ""
        known_slugs = set(
            session.scalars(
                select(LeetCodeProblem.slug).where(LeetCodeProblem.user_id == user_id)
            ).all()
        )

    full_scan = (
        previous_count is None
        or previous_username.casefold() != username.casefold()
        or solved_count < previous_count
    )
    target = solved_count if full_scan else solved_count - previous_count
    all_solved = fetch_solved_questions(session_cookie) if target > 0 or full_scan else {}
    if full_scan and len(all_solved) != solved_count:
        raise RuntimeError(
            "LeetCode's solved-problem list does not match its profile count. "
            "No import checkpoint was changed; try again later."
        )
    new_problems = {
        slug: question
        for slug, question in all_solved.items()
        if slug not in known_slugs
    }
    if not full_scan and len(new_problems) != target:
        raise RuntimeError(
            "LeetCode's solved-problem list does not match the new-solve count. "
            "No import checkpoint was changed; try again later."
        )

    now = datetime.now(timezone.utc)
    added = already_tracked = registered = 0
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise RuntimeError("Revizo account was not found. Please sign in again.")

        imported = {
            item.slug: item
            for item in session.scalars(
                select(LeetCodeProblem).where(LeetCodeProblem.user_id == user_id)
            ).all()
        }
        existing_problems = {
            problem.problem_id: problem
            for problem in session.scalars(
                select(Problem).where(Problem.user_id == user_id)
            ).all()
        }
        for slug, entry in new_problems.items():
            if slug in imported:
                continue
            problem_id = f"lc-{slug}"
            difficulty = entry.get("difficulty", "medium")
            title = entry.get("title") or slug
            topics = entry.get("topics", [])
            problem = existing_problems.get(problem_id)
            if problem is None:
                problem = service.add_problem(
                    session,
                    user_id=user_id,
                    problem_id=problem_id,
                    problem_link=f"https://leetcode.com/problems/{slug}/",
                    difficulty=difficulty,
                    problem_description=title,
                    topics=topics,
                )
                problem.solved = True
                # The authenticated solved-problem list has no per-problem AC
                # date. Start the revision schedule from the import date.
                imported_date = now.date()
                problem.last_solved = imported_date
                problem.repetitions = 1
                problem.interval_days = srs.ladder_for(problem.difficulty)[0]
                added += 1
            else:
                already_tracked += 1
                if not problem.solved:
                    problem.solved = True
                    imported_date = now.date()
                    problem.last_solved = imported_date
                    problem.interval_days = srs.next_interval(
                        problem.difficulty, problem.repetitions, True
                    )
                    problem.repetitions += 1
            session.add(
                LeetCodeProblem(
                    user_id=user_id,
                    slug=slug,
                    title=title,
                    difficulty=difficulty,
                    topics=topics,
                    problem_pk=problem.id,
                    imported_at=now,
                )
            )
            registered += 1

        state = session.get(LeetCodeSyncState, user_id)
        if state is None:
            state = LeetCodeSyncState(user_id=user_id)
            session.add(state)
        state.username = username
        state.solved_count = solved_count
        state.last_synced_at = now
        user.leetcode_username = username
        user.last_synced_at = now.date()
        session.commit()

    return {
        "username": username,
        "total_solved": solved_count,
        "newly_solved": len(new_problems),
        "added_to_tracker": added,
        "already_tracked": already_tracked,
        "import_records_added": registered,
        "mode": "full" if full_scan else "incremental",
    }
