import json
import logging
from datetime import date
from typing import Literal

from mcp.server.mcpserver import MCPServer, Context

from app import jwtauth
from app import service
from app.database import SessionLocal
from app.leetcode_sync import fetch_submissions, sync_recent_ac
from app.models import User

logger = logging.getLogger("learnersmcp")

MISTAKE_TAG = Literal[
    "complexity_tle",
    "edge_cases",
    "off_by_one",
    "overflow",
    "misread_constraints",
    "wrong_ds",
    "math_error",
    "implementation_bug",
    "other",
]

Difficulty = Literal["easy", "medium", "hard"]

mcp = MCPServer(
    name="Revizo",
    title="Revizo - DSA Revision Coach",
    description=(
        "Spaced-repetition tracker for DSA problems. Store problems, record attempts "
        "and mistakes, surface due revisions, track weak spots, and sync LeetCode history. "
        "Each signed-in user has their own private tracker."
    ),
    instructions=(
        "You are a DSA revision coach backed by a spaced-repetition tracker. The signed-in "
        "user's entire history is private to them; never reference data from other accounts.\n\n"
        "DAILY SESSION FLOW\n"
        "1. Start with revision_stats + get_due_problems. Present the due list as the day's "
        "plan ('You have N revisions due; 2 of them you last failed').\n"
        "2. Work through problems ONE AT A TIME. For each: if it was attempted before, ALWAYS "
        "read its watch_out/mistakes aloud first and ask the user to consciously avoid those "
        "patterns. If the user is stuck, offer get_leetcode_submissions to diagnose repeated "
        "failures from their real submission history and code.\n"
        "3. Immediately after EACH attempt (solve or fail), call record_attempt in the same "
        "turn. Never batch attempts. Write mistakes in the user's own words; pick mistake_tags "
        "only from the fixed vocabulary.\n"
        "4. A failed attempt means the problem returns tomorrow carrying its mistakes - tell "
        "the user explicitly ('we'll see this one again tomorrow; watch out for <tags>').\n\n"
        "WHEN TO USE WHICH TOOL\n"
        "- get_due_problems: the primary 'what should I revise today' entry point.\n"
        "- get_backlog: 'give me something new' - never-solved material, oldest first. Do NOT "
        "confuse with due revisions.\n"
        "- add_problem: user starts a new problem. problem_id: lc-<slug> for LeetCode "
        "problems, tracker IDs otherwise. Duplicates are rejected.\n"
        "- record_attempt: exactly once per attempt. solved=true advances the interval "
        "ladder; failure resets to ~1 day and returns the problem to tomorrow's due list.\n"
        "- get_problem: drill into one problem; includes attempt history.\n"
        "- list_problems_by_topic: topics match EXACTLY (case-insensitive): 'dp' not "
        "'dynamic programming'. No fuzzy match.\n"
        "- get_common_mistakes: call proactively BEFORE a new problem to warn the user "
        "about their dominant weak patterns.\n"
        "- Coaching style per problem: restate it briefly, give the link, topic tags and "
        "past mistakes, let the user attempt, nudge toward complexity analysis rather than "
        "just handing the answer.\n\n"
        "SCHEDULING SEMANTICS (explain simply when relevant)\n"
        "success advances the interval ladder for that difficulty "
        "(easy 1,3,7,14,30,60,120 d; medium 1,2,4,8,16,35,70 d; hard 1,2,3,6,12,25,50 d).\n"
        "failure resets to 1 day and attaches mistakes as watch_out for the next revision.\n\n"
        "LEETCODE\n"
        "- sync_leetcode imports recent ACs (public data; hard cap 50, public API exposes "
        "~20). First sync needs the user's LeetCode ID: ask, pass explicitly, it is "
        "remembered.\n"
        "- When the user is stuck or failing repeatedly, offer to pull their submissions "
        "via get_leetcode_submissions and read the code to find what keeps breaking.\n"
        "- Proactively warn about patterns from get_common_mistakes on NEW problems "
        "('you keep hitting edge_cases - check empty inputs and boundaries first').\n\n"
        "TONE: encouraging coach, concise, data-grounded. Always cite the user's own "
        "numbers and mistakes - the tracker's point is that revision is personal."
    ),
    version="0.3.0",
)


def _with_session(fn):
    session = SessionLocal()
    try:
        result = fn(session)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _current_user_id(ctx: Context) -> int:
    headers = dict(ctx.headers or {})
    token = headers.get("authorization", "")
    if not token.lower().startswith("bearer "):
        raise RuntimeError(
            "Not authenticated. Connect this MCP server via OAuth (Add to Cursor button / sign in) - "
            "every tool call needs your personal Bearer token."
        )
    try:
        claims = jwtauth.verify_access_token(token[7:].strip())
        return int(claims["sub"])
    except Exception as e:
        raise RuntimeError(f"Invalid or expired session - reconnect via OAuth to refresh. ({e})") from e


def _dump_problem(session, user_id, p, with_watch_out=True) -> dict:
    data = {
        "problem_id": p.problem_id,
        "problem_link": p.problem_link,
        "difficulty": p.difficulty,
        "description": p.problem_description,
        "topics": p.topics,
        "solved": p.solved,
        "last_solved": p.last_solved.isoformat() if p.last_solved else None,
        "interval_days": p.interval_days,
        "repetitions": p.repetitions,
        "mistakes": p.mistakes,
    }
    if with_watch_out:
        data["watch_out"] = service.build_watch_out(session, user_id, p)
    return data


@mcp.tool()
def add_problem(
    problem_id: str,
    problem_link: str,
    difficulty: Difficulty,
    problem_description: str,
    topics: list[str],
    ctx: Context = None,
) -> str:
    """Store a NEW problem the user is starting to solve.
    Use when: the user begins a problem that is not yet in the tracker.
    problem_id convention: 'lc-<slug>' for LeetCode problems, tracker-style IDs otherwise.
    topics: list of topic strings (e.g. ['Array', 'Hash Table']). difficulty: easy/medium/hard.
    Duplicate problem_ids are rejected; use get_problem to check first. Read-only-ish otherwise."""
    user_id = _current_user_id(ctx)
    try:

        def add(session):
            problem = service.add_problem(
                session, user_id, problem_id, problem_link, difficulty, problem_description, topics
            )
            return _dump_problem(session, user_id, problem, with_watch_out=False)

        data = _with_session(add)
    except ValueError as e:
        return f"Error: {e}"
    return f"Stored problem: {json.dumps(data)}"


@mcp.tool()
def record_attempt(
    problem_id: str,
    solved: bool,
    mistakes: str | None = None,
    mistake_tags: list[MISTAKE_TAG] | None = None,
    ctx: Context = None,
) -> str:
    """Record ONE attempt on a problem and RESCHEDULE it - MUTATING tool.
    Use when: the user finishes an attempt (either solve or fail), right after it happens; never batch.
    solved=true advances the revision ladder; solved=false resets to ~1 day and brings the problem back to
    tomorrow's due list carrying mistakes as watch_out. mistakes: quote the user's own words. mistake_tags:
    structured patterns chosen ONLY from this vocabulary: complexity_tle, edge_cases, off_by_one, overflow,
    misread_constraints, wrong_ds, math_error, implementation_bug, other. Repeating a past tag triggers a warning."""
    user_id = _current_user_id(ctx)
    try:

        def record(session):
            result = service.record_attempt(
                session, user_id, problem_id, solved, mistakes, mistake_tags
            )
            return {
                "problem": _dump_problem(session, user_id, result["problem"]),
                "repeated_tags": result["repeated_tags"],
            }

        data = _with_session(record)
    except ValueError as e:
        return f"Error: {e}"

    text = json.dumps(data)
    if data["repeated_tags"]:
        text = (
            f"WARNING: you are repeating mistake patterns: {', '.join(data['repeated_tags'])}. "
            f"Don't repeat them again. {text}"
        )
    return f"Attempt recorded: {text}"


@mcp.tool()
def get_due_problems(limit: int = 10, ctx: Context = None) -> str:
    """Problems due for REVISION today, prioritized (most overdue first, then hardest, then mistake-prone),
    each carrying a watch_out reminder of last mistakes.
    Use when: user asks what to revise today, or at session start alongside revision_stats.
    Read-only. This is different from get_backlog (fresh unsolved material)."""
    user_id = _current_user_id(ctx)

    def get(session):
        return [
            _dump_problem(session, user_id, p)
            for p in service.get_due_problems(session, user_id, date.today(), limit)
        ]

    problems = _with_session(get)
    if not problems:
        return "Nothing due for revision. Add problems or enjoy the streak."
    return json.dumps(problems)


@mcp.tool()
def get_backlog(ctx: Context = None) -> str:
    """All never-solved problems (the fresh-material backlog), ordered oldest first.
    Use when: the user wants NEW problems to attack, not scheduled revisions. Read-only.
    Distinct from get_due_problems (which is spaced-repetition revision of previously attempted ones)."""
    user_id = _current_user_id(ctx)

    def get(session):
        return [
            _dump_problem(session, user_id, p, with_watch_out=False)
            for p in service.get_backlog(session, user_id)
        ]

    problems = _with_session(get)
    if not problems:
        return "Backlog is empty. Add problems with add_problem."
    return json.dumps(problems, default=str)


@mcp.tool()
def get_problem(problem_id: str, ctx: Context = None) -> str:
    """Full details of ONE problem: SRS state, watch_out reminder and complete attempt history.
    Use when: drilling into a specific problem before/after an attempt, or to check whether a
    problem_id already exists before add_problem. Read-only. Needs the exact problem_id."""
    user_id = _current_user_id(ctx)

    def get(session):
        problem = service.get_problem(session, user_id, problem_id)
        if problem is None:
            return None
        data = _dump_problem(session, user_id, problem)
        data["attempt_history"] = [
            {
                "date": a.attempt_date.isoformat(),
                "solved": a.solved,
                "mistakes": a.mistakes,
                "tags": a.mistake_tags,
            }
            for a in service.get_attempt_history(session, user_id, problem)
        ]
        return data

    data = _with_session(get)
    if data is None:
        return f"Error: Problem '{problem_id}' not found"
    return json.dumps(data)


@mcp.tool()
def list_problems_by_topic(topic: str, ctx: Context = None) -> str:
    """All problems whose topics include the given topic (case-insensitive EXACT match).
    Use when: the user wants to focus a topic (e.g. 'Arrays', 'DP', 'Binary Search').
    Note: 'dp' will NOT match stored 'Dynamic Programming' - match the stored wording; when in doubt
    call get_problem on a known problem to see its stored topic strings. Read-only."""
    user_id = _current_user_id(ctx)

    def get(session):
        return [
            _dump_problem(session, user_id, p, with_watch_out=False)
            for p in service.list_problems_by_topic(session, user_id, topic)
        ]

    problems = _with_session(get)
    if not problems:
        return f"No problems found for topic '{topic}'."
    return json.dumps(problems, default=str)


@mcp.tool()
def revision_stats(ctx: Context = None) -> str:
    """One call overview of the tracker: total, solved, backlog, due_today, by_difficulty.
    Use when: session starts (with get_due_problems) or the user asks for overall progress.
    Read-only."""
    user_id = _current_user_id(ctx)
    return json.dumps(_with_session(lambda s: service.revision_stats(s, user_id)))


@mcp.tool()
def get_common_mistakes(limit: int = 5, ctx: Context = None) -> str:
    """Ranked mistake patterns across ALL the user's attempts - their known weak points,
    with counts, last-seen dates and recent example problems.
    Use when: BEFORE starting a new problem (warn proactively) or when the user asks what they
    keep doing wrong. Read-only."""
    user_id = _current_user_id(ctx)
    return json.dumps(_with_session(lambda s: service.get_common_mistakes(s, user_id, limit)))


@mcp.tool()
def sync_leetcode(username: str | None = None, limit: int = 50, ctx: Context = None) -> str:
    """Import the user's recent LeetCode solved problems into their tracker (LIMIT hard-capped at 50 -
    the public LeetCode API only exposes the ~20 most recent ACs anyway). MUTATING.
    Use when: user asks to sync/import their LeetCode progress. Automatically reuses the stored
    LeetCode username; if none is on file you MUST ask the user for their LeetCode ID in chat and
    pass it here once - it is then remembered for all future syncs. Idempotent: already-known
    problems are skipped, so re-syncing only adds new solves."""
    user_id = _current_user_id(ctx)
    limit = min(limit, 50)

    user = _with_session(lambda s: s.get(User, user_id))
    stored = (user.leetcode_username or "").strip() if user else ""
    effective = (username or "").strip() or stored
    if not effective:
        return (
            "Error: No LeetCode username on file for this account. Ask the user for their "
            "LeetCode ID (their public profile handle) and call sync_leetcode(username=...) once."
        )

    try:
        result = sync_recent_ac(limit=limit, username=effective, user_id=user_id)
    except RuntimeError as e:
        return f"Error: {e}"

    def store(session):
        u = session.get(User, user_id)
        if u is not None:
            u.leetcode_username = effective
            u.last_synced_at = date.today()
            session.add(u)

    _with_session(store)
    return json.dumps(result)


@mcp.tool()
def get_leetcode_submissions(
    problem_id: str, limit: int = 10, with_code: bool = True, ctx: Context = None
) -> str:
    """The user's REAL LeetCode submission history for one problem: statuses (AC/WA/TLE/RE),
    languages, runtimes, dates - plus the source code of recent submissions (with_code=true)
    to pinpoint what keeps going wrong. Requires the user's LEETCODE_SESSION cookie on file
    (collected on the connect page); otherwise returns an instructive error.
    Use when: the user is stuck or failing repeatedly on a problem and diagnosis from their
    actual attempts would help. High-value but heavier response - prefer offering it before
    pulling unasked. Read-only."""
    user_id = _current_user_id(ctx)

    def get(session):
        return service.get_problem(session, user_id, problem_id)

    problem = _with_session(get)
    if problem is None:
        return f"Error: Problem '{problem_id}' not found"
    slug = problem.problem_link.rstrip("/").split("/")[-1]

    def get_cookie(session):
        user = session.get(User, user_id)
        return user.leetcode_session if user else ""

    cookie = _with_session(get_cookie)
    try:
        data = fetch_submissions(slug, limit=limit, with_code=with_code, session_cookie=cookie)
    except Exception as e:
        logger.warning("leetcode submissions fetch failed: %s", e)
        return f"Error fetching LeetCode submissions: {e}"
    return json.dumps({"problem_id": problem_id, "slug": slug, "submissions": data})
