import json
from datetime import date

import service
from db import SessionLocal
from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    name="learnersMcp",
    title="DSA Revision",
    description=(
        "Spaced-repetition tracker for DSA problems. Store problems you solve, "
        "record attempts and mistakes, get due revisions and a backlog list."
    ),
    version="0.1.0",
)


def _run(fn):
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


def _dump_problem(p) -> dict:
    return {
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
        problem = _run(
            lambda s: service.add_problem(
                s, problem_id, problem_link, difficulty, problem_description, topics
            )
        )
    except ValueError as e:
        return f"Error: {e}"
    return f"Stored problem: {json.dumps(_dump_problem(problem))}"


@mcp.tool()
def record_attempt(problem_id: str, solved: bool, mistakes: str | None = None) -> str:
    """Record an attempt on a problem. On success the revision interval grows; on failure it resets and the problem returns to the due list."""
    try:
        problem = _run(lambda s: service.record_attempt(s, problem_id, solved, mistakes))
    except ValueError as e:
        return f"Error: {e}"
    return f"Attempt recorded: {json.dumps(_dump_problem(problem))}"


@mcp.tool()
def get_due_problems(limit: int = 10) -> str:
    """Problems due for revision today (overdue first, hardest first, mistake-prone prioritized)."""
    problems = _run(lambda s: service.get_due_problems(s, date.today(), limit))
    if not problems:
        return "Nothing due for revision. Add problems or enjoy the streak."
    return json.dumps([_dump_problem(p) for p in problems])


@mcp.tool()
def get_backlog() -> str:
    """All problems not yet solved (the backlog to work through)."""
    problems = _run(service.get_backlog)
    if not problems:
        return "Backlog is empty. Add problems with add_problem."
    return json.dumps([_dump_problem(p) for p in problems])


@mcp.tool()
def get_problem(problem_id: str) -> str:
    """Full details of one problem, including revision state and last mistakes."""
    problem = _run(lambda s: service.get_problem(s, problem_id))
    if problem is None:
        return f"Error: Problem '{problem_id}' not found"
    return json.dumps(_dump_problem(problem))


@mcp.tool()
def list_problems_by_topic(topic: str) -> str:
    """All problems matching a topic, e.g. 'arrays', 'dp', 'graphs'."""
    problems = _run(lambda s: service.list_problems_by_topic(s, topic))
    if not problems:
        return f"No problems found for topic '{topic}'."
    return json.dumps([_dump_problem(p) for p in problems])


@mcp.tool()
def revision_stats() -> str:
    """Counts: total, solved, backlog, due today, breakdown by difficulty."""
    return json.dumps(_run(service.revision_stats))
