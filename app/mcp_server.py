import json
from datetime import date
from typing import Literal

from mcp.server.mcpserver import MCPServer, Context

from app import jwtauth
from app import service
from app.database import SessionLocal
from app.leetcode_sync import sync_recent
from app.models import User
from app.prompts import INSTRUCTIONS

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
    instructions=INSTRUCTIONS,
    version="0.5.8",
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

# this function helps us get the current user id
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


def _dump_problem(session, user_id, p, with_watch_out=True) -> dict: # default with_watch_out is true
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
    # if there is a watch out , we are adding an extra field called that
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
    """Store a NEW problem the user is starting to solve - WITHOUT any attempt outcome.
    This never implies the user solved or failed it. Use when: the user begins a problem
    that is not yet in the tracker. problem_id convention: 'lc-<slug>' for LeetCode
    problems, tracker-style IDs otherwise. topics: list of topic strings (e.g.
    ['Array', 'Hash Table']). difficulty: easy/medium/hard.
    problem_link: use the user's link verbatim; if none was given for a LeetCode problem,
    DERIVE it from the id ('lc-<slug>' -> 'https://leetcode.com/problems/<slug>/'); for
    non-LeetCode material ask the user once, else save with an empty link - never fabricate.
    Duplicate problem_ids are rejected; use get_problem to check first.
    If the user presented an attempt on this new problem, follow with record_attempt
    in the SAME turn (add first, then record)."""
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
    Requires the problem to ALREADY exist - if it is new, call add_problem FIRST, then this
    (both in one turn when the user presents an untracked problem's attempt).
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

# understod : ))
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
        data = _dump_problem(session, user_id, problem) # adds watch miskes also 
        data["attempt_history"] = [
            {
                "date": a.attempt_date.isoformat(),
                "solved": a.solved,
                "mistakes": a.mistakes,
                "tags": a.mistake_tags,
            }
            for a in service.get_attempt_history(session, user_id, problem) # seperate table for this
        ] # this is getting all the previous miskes that was done on this problem
        return data

    data = _with_session(get)
    if data is None:
        return f"Error: Problem '{problem_id}' not found"
    return json.dumps(data)

# : )) understod
@mcp.tool()
def list_problems_by_topic(topic: str, ctx: Context = None) -> str:
    """All problems whose topics include the given topic (case-insensitive EXACT match).
    Use when: the user wants to focus a topic (e.g. 'Arrays', 'DP', 'Binary Search').
    Note: 'dp' will NOT match stored 'Dynamic Programming' - match the stored wording; when in doubt
    call get_problem on a known problem to see its stored topic strings. Read-only."""
    user_id = _current_user_id(ctx) # gets us the current user id
    
    def get(session):
        return [
            # watch out is such a thing that it will tell you where you made a mistake the last time
            
            # watch out here is a methodoly to check the last attempted thing
            _dump_problem(session, user_id, p, with_watch_out=False)
            for p in service.list_problems_by_topic(session, user_id, topic) # for each problem
        ]

    problems = _with_session(get) # we are calling the function that we are passing here as per session 
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



# this one might require some leetcode sessions , so maybe normally i wont be getting the leetcode session id thingy 
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
    """Import the user's recent LeetCode activity into their tracker (LIMIT hard-capped at 50 -
    the public LeetCode API only exposes the ~20 most recent submissions anyway). MUTATING.
    Imports BOTH solved problems (marked solved on their real AC date) AND recent failed
    attempts (as unsolved backlog entries with attempt history), so the coach knows what the
    user is stuck on. Use when: user asks to sync/import their LeetCode progress. Automatically
    reuses the stored LeetCode username; if none is on file you MUST ask the user for their
    LeetCode ID in chat and pass it here once - it is then remembered for all future syncs.
    Idempotent per submission: re-syncing only adds unseen submissions, never duplicates."""
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
        result = sync_recent(limit=limit, username=effective, user_id=user_id)
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
