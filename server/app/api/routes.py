"""JSON API for the React SPA.

Replaces the data-baking that used to happen inside the Jinja page routes.
All handlers reuse the existing service layer (app.service) — no new DB tables
or model changes. Auth is cookie-session based (see deps.get_api_user).
"""

import json
import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app import service
from app.database import SessionLocal
from app.leetcode_sync import import_all_solved, normalize_session_cookie
from app.models import Attempt, Problem, User
from app.secret_storage import (
    SecretStorageError,
    decrypt_leetcode_session,
    encrypt_leetcode_session,
)
from app.srs import is_due, overdue_days
from app.web.csv_import import MAX_FILE_BYTES, parse_csv
from app.web.deps import UserContext

from app.oauth_server import SUPABASE_ANON_KEY, SUPABASE_URL

# Reused by the public Landing/docs pages to decide whether to show sign-in.
_PROVIDER = os.getenv("SUPABASE_OAUTH_PROVIDER", "google")

from .deps import get_api_user
from .schemas import (
    AddProblemIn,
    AttemptOut,
    DashboardData,
    DashboardRow,
    DueCard,
    LeetCodeSettingsIn,
    LeetCodeStatus,
    ProblemOut,
    SessionUser,
    SolveIn,
    Stats,
    StudyPlanSettingsIn,
    WeakPoint,
)

router = APIRouter()


# ---------------------------------------------------------------- session


@router.get("/me")
def me(user: UserContext = Depends(get_api_user)) -> SessionUser:
    return SessionUser(id=user.id, email=user.email, display_name=user.display_name)


# ---------------------------------------------------------------- dashboard


def _problem_out(p: Problem, with_watch_out: str | None = None) -> ProblemOut:
    return ProblemOut(
        problem_id=p.problem_id,
        problem_link=p.problem_link,
        difficulty=p.difficulty,
        problem_description=p.problem_description,
        topics=list(p.topics or []),
        solved=p.solved,
        last_solved=p.last_solved.isoformat() if p.last_solved else None,
        interval_days=p.interval_days,
        repetitions=p.repetitions,
        mistakes=p.mistakes,
        watch_out=with_watch_out,
    )


def _visible(p: Problem, difficulty: str, status: str, topic: str, today: date) -> bool:
    if difficulty and p.difficulty != difficulty:
        return False
    if topic and not any(topic.lower() == t.lower() for t in (p.topics or [])):
        return False
    if status == "solved" and not p.solved:
        return False
    if status == "backlog" and p.solved:
        return False
    if status == "due" and not is_due(p.last_solved, p.interval_days, p.solved, today):
        return False
    return True


@router.get("/dashboard")
def dashboard(
    user: UserContext = Depends(get_api_user),
    difficulty: str = "",
    status: str = "",
    topic: str = "",
) -> DashboardData:
    today = date.today()
    topic = (topic or "").strip()

    with SessionLocal() as session:
        data = service.dashboard_data(session, user.id, today=today)
        problems = data["problems"]
        history_map = data["history"]

        rows = [
            DashboardRow(
                p=_problem_out(p),
                due=is_due(p.last_solved, p.interval_days, p.solved, today),
                history=[
                    AttemptOut(
                        date=a.attempt_date.isoformat(),
                        solved=a.solved,
                        mistakes=a.mistakes,
                        tags=list(a.mistake_tags or []),
                    )
                    for a in history_map.get(p.id, [])
                ],
            )
            for p in problems
            if _visible(p, difficulty, status, topic, today)
        ]

        due_cards = []
        for p in data["due_problems"]:
            days = overdue_days(p.last_solved, p.interval_days, today)
            when = (
                "never attempted"
                if p.last_solved is None
                else (f"{days}d overdue" if days else "due today")
            )
            due_cards.append(
                DueCard(p=_problem_out(p), watch_out=data["watch_outs"].get(p.id), when=when)
            )

        max_count = max((v["count"] for v in data["weak"].values()), default=0) or 1
        weak_points = [
            WeakPoint(
                tag=tag,
                count=v["count"],
                last_seen=v["last_seen"],
                recent_problems=list(v["recent_problems"]),
                pct=round(v["count"] / max_count * 100),
            )
            for tag, v in data["weak"].items()
        ]

    stats = Stats(
        total=data["stats"]["total"],
        solved=data["stats"]["solved"],
        backlog=data["stats"]["backlog"],
        due_today=data["stats"]["due_today"],
        by_difficulty=data["stats"]["by_difficulty"],
    )

    return DashboardData(
        stats=stats,
        due=due_cards,
        weak_points=weak_points,
        rows=rows,
        today_long=today.strftime("%A, %B %d"),
        filters={"difficulty": difficulty, "status": status, "topic": topic},
    )


# ---------------------------------------------------------------- problems


@router.post("/problems")
def add_problem(payload: AddProblemIn, user: UserContext = Depends(get_api_user)):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Give the problem a title.")
    topics = [t.strip() for t in payload.topics.split(",") if t.strip()]
    with SessionLocal() as session:
        try:
            service.add_problem(
                session,
                user.id,
                problem_id=title,
                problem_link=payload.link.strip(),
                difficulty=payload.difficulty.strip() or "medium",
                problem_description=payload.description,
                topics=topics,
            )
            session.commit()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e) or "That problem is already being tracked.")
    return {"ok": True}


# ---------------------------------------------------------------- leetcode


@router.get("/leetcode")
def leetcode_status(user: UserContext = Depends(get_api_user)) -> LeetCodeStatus:
    with SessionLocal() as session:
        account = session.get(User, user.id)
        connected = bool(account and account.leetcode_session)
        username = (account.leetcode_username or "") if account else ""
    return LeetCodeStatus(connected=connected, username=username)


@router.post("/leetcode/settings")
def save_leetcode_settings(
    payload: LeetCodeSettingsIn, user: UserContext = Depends(get_api_user)
) -> LeetCodeStatus:
    username = payload.username.strip()
    raw_cookie = (payload.session_cookie or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Enter your LeetCode username.")

    try:
        encrypted_cookie = (
            encrypt_leetcode_session(normalize_session_cookie(raw_cookie)) if raw_cookie else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SecretStorageError as e:
        raise HTTPException(status_code=503, detail=str(e))

    with SessionLocal() as session:
        account = session.get(User, user.id)
        if account is None:
            raise HTTPException(status_code=404, detail="Your account could not be found. Please sign in again.")
        account.leetcode_username = username
        if encrypted_cookie is not None:
            account.leetcode_session = encrypted_cookie
        session.commit()
        connected = bool(account.leetcode_session)
        uname = account.leetcode_username or ""
    return LeetCodeStatus(connected=connected, username=uname, notice="LeetCode settings saved.")


@router.post("/leetcode/disconnect")
def disconnect_leetcode(user: UserContext = Depends(get_api_user)) -> LeetCodeStatus:
    username = ""
    with SessionLocal() as session:
        account = session.get(User, user.id)
        if account is not None:
            account.leetcode_session = ""
            session.commit()
            username = account.leetcode_username or ""
    return LeetCodeStatus(connected=False, username=username, notice="LeetCode session removed.")


@router.post("/leetcode/import")
async def import_leetcode(user: UserContext = Depends(get_api_user)):
    with SessionLocal() as session:
        account = session.get(User, user.id)
        username = (account.leetcode_username or "").strip() if account else ""
        encrypted_cookie = account.leetcode_session if account else ""
    if not username or not encrypted_cookie:
        raise HTTPException(
            status_code=400,
            detail="Add your LeetCode username and session cookie before importing.",
        )
    try:
        session_cookie = decrypt_leetcode_session(encrypted_cookie)
        result = await run_in_threadpool(
            import_all_solved, username=username, session_cookie=session_cookie, user_id=user.id
        )
    except (RuntimeError, SecretStorageError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"connected": True, "username": username, "result": result}


# ---------------------------------------------------------------- csv import


SAMPLE_CSV = (
    "Problem,Link,Difficulty,Topics,Description\n"
    "Two Sum,https://leetcode.com/problems/two-sum/,easy,\"arrays, hashing\","
    "Find two numbers adding up to the target.\n"
    "Coin Change,https://leetcode.com/problems/coin-change/,medium,dp,"
    "Fewest coins to make up an amount.\n"
)


@router.get("/import/sample.csv")
def import_sample_csv():
    """Downloadable template so users can fill in a correct CSV directly."""
    return Response(
        SAMPLE_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="revizo_import_template.csv"'},
    )


@router.post("/import")
async def import_problems(file: UploadFile = File(...), user: UserContext = Depends(get_api_user)):
    """Stream CSV import progress as Server-Sent Events.

    Mirrors the old /app/import behaviour: parse → add each row (dedup on
    duplicates) → emit start/progress/done events the React UI renders live.
    """
    data = await file.read()
    if (file.filename or "").lower().endswith(".csv") is False:
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File is too large — keep it under 1 MB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400, detail="That file isn't valid UTF-8 text — re-save it as a plain CSV."
        )

    try:
        parsed = parse_csv(text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not parsed.rows:
        raise HTTPException(
            status_code=400,
            detail="No importable problems found — every row needs both a problem and a link.",
        )

    async def event_stream():
        imported, duplicates, failed = 0, 0, []
        total = len(parsed.rows)
        yield f"data: {json.dumps({'type': 'start', 'total': total, 'skipped': len(parsed.skipped)})}\n\n"

        with SessionLocal() as session:
            for i, row in enumerate(parsed.rows):
                try:
                    service.add_problem(
                        session,
                        user.id,
                        problem_id=row["title"],
                        problem_link=row["link"],
                        difficulty=row["difficulty"],
                        problem_description=row["description"],
                        topics=row["topics"],
                    )
                    imported += 1
                except ValueError:
                    duplicates += 1
                except Exception:
                    failed.append(row["title"])

                # Emit after every row so even a 2-row import shows movement
                # (the old every-10-rows rule made small imports look stuck).
                yield f"data: {json.dumps({'type': 'progress', 'processed': i + 1, 'total': total, 'imported': imported, 'duplicates': duplicates})}\n\n"
            session.commit()

        summary = {
            "type": "done",
            "imported": imported,
            "duplicates": duplicates,
            "skipped": [{"row_number": s.row_number, "reason": s.reason} for s in parsed.skipped],
            "extras_ignored": parsed.extras_ignored,
            "too_many_rows": parsed.too_many_rows,
            "failed": failed,
        }
        yield f"data: {json.dumps(summary)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ------------------------------------------------------------- study plan


def _serialize_problem(p) -> dict:
    return {
        "problem_id": p.problem_id,
        "problem_link": p.problem_link,
        "difficulty": p.difficulty,
        "problem_description": p.problem_description,
        "topics": p.topics or [],
        "solved": p.solved,
        "last_solved": p.last_solved.isoformat() if p.last_solved else None,
        "interval_days": p.interval_days,
        "repetitions": p.repetitions,
        "mistakes": p.mistakes or "",
        "watch_out": None,
    }


def _plan_payload(plan: dict) -> dict:
    return {
        "settings": plan["settings"],
        "old_target": plan["old_target"],
        "old_solved_today": plan["old_solved_today"],
        "new_target": plan["new_target"],
        "new_solved_today": plan["new_solved_today"],
        "old_suggestions": [_serialize_problem(p) for p in plan["old_suggestions"]],
        "new_suggestions": [_serialize_problem(p) for p in plan["new_suggestions"]],
        "weak_topics": plan["weak_topics"],
        "streak": plan["streak"],
    }


@router.get("/study-plan")
def study_plan(user: UserContext = Depends(get_api_user)) -> dict:
    with SessionLocal() as session:
        plan = service.build_study_plan(session, user.id)
    return _plan_payload(plan)


@router.post("/study-plan/settings")
def save_study_plan_settings(
    payload: StudyPlanSettingsIn, user: UserContext = Depends(get_api_user)
) -> dict:
    with SessionLocal() as session:
        strategy = service.update_strategy(
            session, user.id, payload.revisions_per_session, payload.backlog_per_session
        )
        session.commit()
        return {
            "revisions_per_session": strategy.revisions_per_session,
            "backlog_per_session": strategy.backlog_per_session,
            "notice": "Plan settings saved.",
        }


@router.post("/problems/{problem_id}/solve")
def solve_problem(
    problem_id: str, payload: SolveIn, user: UserContext = Depends(get_api_user)
) -> dict:
    with SessionLocal() as session:
        service.record_attempt(
            session,
            user.id,
            problem_id,
            solved=payload.solved,
            mistakes=payload.mistakes,
            mistake_tags=payload.mistake_tags,
        )
        session.commit()
        plan = service.build_study_plan(session, user.id)
    return _plan_payload(plan)


# Public (no auth): tells the Landing/docs pages whether sign-in is configured.
@router.get("/meta")
def meta() -> dict:
    return {
        "oauth_configured": bool(SUPABASE_URL and SUPABASE_ANON_KEY),
        "provider": _PROVIDER,
    }
