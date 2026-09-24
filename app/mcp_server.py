import json
import logging
from datetime import date

from app import service
from app.database import SessionLocal
from app.leetcode_sync import fetch_submissions, sync_recent_ac
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

logger = logging.getLogger("learnersmcp")

mcp = MCPServer(
    name="learnersMcp",
    title="DSA Revision Coach",
    description=(
        "Spaced-repetition tracker for DSA problems. Store problems, record attempts "
        "and mistakes, surface due revisions, track weak spots, and sync LeetCode history."
    ),
    instructions=(
        "Before the user works on a problem they have attempted before, ALWAYS warn them "
        "about their recorded mistakes (watch_out / mistakes fields) and check whether "
        "their new approach would repeat them. When recording attempts, infer structured "
        "mistake_tags from failures. If the user is stuck on a problem, use "
        "get_leetcode_submissions to review their actual submission history and code."
    ),
    version="0.2.0",
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


def _dump_problem(session, p, with_watch_out=True) -> dict:
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
        data["watch_out"] = service.build_watch_out(session, p)
    return data


@mcp.tool()
def add_problem(
    problem_id: str,
    problem_link: str,
    difficulty: str,
    problem_description: str,
    topics: list[str],
) -> str:
    """Store a new DSA problem you are solving. difficulty: easy/medium/hard."""
    try:

        def add(session):
            problem = service.add_problem(
                session, problem_id, problem_link, difficulty, problem_description, topics
            )
            return _dump_problem(session, problem, with_watch_out=False)

        data = _with_session(add)
    except ValueError as e:
        return f"Error: {e}"
    return f"Stored problem: {json.dumps(data)}"


@mcp.tool()
def record_attempt(
    problem_id: str,
    solved: bool,
    mistakes: str | None = None,
    mistake_tags: list[str] | None = None,
) -> str:
    """Record an attempt on a problem and reschedule it. mistake_tags: structured patterns from this vocabulary: complexity_tle, edge_cases, off_by_one, overflow, misread_constraints, wrong_ds, math_error, implementation_bug, other."""
    try:

        def record(session):
            result = service.record_attempt(session, problem_id, solved, mistakes, mistake_tags)
            return {"problem": _dump_problem(session, result["problem"]), "repeated_tags": result["repeated_tags"]}

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
def get_due_problems(limit: int = 10) -> str:
    """Problems due for revision today (overdue first, hardest first, mistake-prone prioritized), each with a watch_out reminder of past mistakes."""
    def get(session):
        return [
            _dump_problem(session, p) for p in service.get_due_problems(session, date.today(), limit)
        ]

    problems = _with_session(get)
    if not problems:
        return "Nothing due for revision. Add problems or enjoy the streak."
    return json.dumps(problems)


@mcp.tool()
def get_backlog() -> str:
    """All problems not yet solved (the backlog to work through), ordered oldest first."""
    def get(session):
        return [_dump_problem(session, p, with_watch_out=False) for p in service.get_backlog(session)]

    problems = _with_session(get)
    if not problems:
        return "Backlog is empty. Add problems with add_problem."
    return json.dumps(problems)


@mcp.tool()
def get_problem(problem_id: str) -> str:
    """Full details of one problem: revision state, watch_out reminder, and attempt history."""
    def get(session):
        problem = service.get_problem(session, problem_id)
        if problem is None:
            return None
        data = _dump_problem(session, problem)
        data["attempt_history"] = [
            {
                "date": a.attempt_date.isoformat(),
                "solved": a.solved,
                "mistakes": a.mistakes,
                "tags": a.mistake_tags,
            }
            for a in service.get_attempt_history(session, problem)
        ]
        return data

    data = _with_session(get)
    if data is None:
        return f"Error: Problem '{problem_id}' not found"
    return json.dumps(data)


@mcp.tool()
def list_problems_by_topic(topic: str) -> str:
    """All problems matching a topic, e.g. 'arrays', 'dp', 'graphs'."""
    def get(session):
        return [
            _dump_problem(session, p, with_watch_out=False)
            for p in service.list_problems_by_topic(session, topic)
        ]

    problems = _with_session(get)
    if not problems:
        return f"No problems found for topic '{topic}'."
    return json.dumps(problems)


@mcp.tool()
def revision_stats() -> str:
    """Counts: total, solved, backlog, due today, breakdown by difficulty."""
    return json.dumps(_with_session(service.revision_stats))


@mcp.tool()
def get_common_mistakes(limit: int = 5) -> str:
    """The user's most common mistake patterns across all attempts - weak points. Use these to proactively warn the user, also on NEW problems."""
    return json.dumps(_with_session(lambda s: service.get_common_mistakes(s, limit)))


@mcp.tool()
def sync_leetcode(username: str, limit: int = 200) -> str:
    """Import a user's recently solved LeetCode problems (public profile data). Idempotent: existing problems are skipped. You MUST ask the user for their LeetCode username before calling this - never call it without an explicitly provided ID, never guess or assume one."""
    try:
        return json.dumps(sync_recent_ac(limit=limit, username=username))
    except RuntimeError as e:
        return f"Error: {e}"


@mcp.tool()
def get_leetcode_submissions(problem_id: str, limit: int = 10, with_code: bool = True) -> str:
    """Fetch the user's actual LeetCode submission history for one problem (private data; needs LEETCODE_SESSION in .env). Includes code of recent submissions for diagnosing what keeps going wrong."""
    problem = _with_session(lambda s: service.get_problem(s, problem_id))
    if problem is None:
        return f"Error: Problem '{problem_id}' not found"
    slug = problem.problem_link.rstrip("/").split("/")[-1]
    try:
        data = fetch_submissions(slug, limit=limit, with_code=with_code)
    except Exception as e:
        logger.warning("leetcode submissions fetch failed: %s", e)
        return f"Error fetching LeetCode submissions: {e}"
    return json.dumps({"problem_id": problem_id, "slug": slug, "submissions": data})
