"""Web dashboard routes.

Login reuses the MCP-spec OAuth flow: the web app acts as just another OAuth
client of this server's own /oauth/* endpoints. /login generates PKCE + state,
/oauth/authorize bridges to Supabase (Google), /oauth/callback mints a
short-lived auth code JWT, and /auth/callback (web-only) turns that auth code
into an HttpOnly session cookie — no /oauth/token round-trip needed, since
/oauth/callback has already verified PKCE by the time it issues the code.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import urllib.parse
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import jwtauth, service
from app.database import SessionLocal
from app.oauth_server import (
    APP_BASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
    _issuer_from_request,
    ensure_web_client,
)
from app.srs import is_due, overdue_days
from app.web.deps import SESSION_COOKIE, UserContext, require_user

logger = logging.getLogger("learnersmcp")

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Cache-busted stylesheet URL: the hash changes on every rebuild, so browsers
# can cache /app.css aggressively without ever serving stale styles.
try:
    _css_hash = hashlib.sha256(
        (Path(__file__).parents[2] / "public" / "app.css").read_bytes()
    ).hexdigest()[:8]
except FileNotFoundError:
    _css_hash = "dev"
templates.env.globals["CSS_URL"] = f"/app.css?v={_css_hash}"

PKCE_COOKIE = "lr_pkce"
STATE_COOKIE = "lr_state"
SESSION_MAX_AGE = jwtauth.access_token_seconds


def _cookie_flags() -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": APP_BASE_URL.startswith("https://"),
        "path": "/",
    }


def _error(request: Request, title: str, message: str, status: int = 400):
    return templates.TemplateResponse(
        request, "error.html", {"title": title, "message": message}, status_code=status
    )


# ---------------------------------------------------------------- landing/auth


@router.get("/", response_class="text/html; charset=utf-8")
async def landing(request: Request):
    oauth_ready = bool(SUPABASE_URL and SUPABASE_ANON_KEY)
    return templates.TemplateResponse(request, "landing.html", {"oauth_ready": oauth_ready})


@router.get("/login")
async def login(request: Request):
    if not (SUPABASE_URL and SUPABASE_ANON_KEY):
        return _error(
            request,
            "Sign-in unavailable",
            "OAuth is not configured on this server yet — set SUPABASE_URL and "
            "SUPABASE_ANON_KEY and enable a Google provider in Supabase.",
            status=503,
        )

    # Pin the flow to the origin the browser is actually on. Cookies are
    # host-scoped: if the round-trip returned to a different host than the one
    # that started login (localhost vs 127.0.0.1 vs a deploy URL), the state
    # cookie would vanish and /auth/callback would reject the sign-in.
    issuer = _issuer_from_request(request)
    redirect_uri = f"{issuer}/auth/callback"
    try:
        client = ensure_web_client([redirect_uri])
    except Exception as e:
        logger.warning("web client registration failed: %s", e)
        return _error(
            request,
            "Sign-in unavailable",
            "Could not reach the database to register the web client. Try again shortly.",
            status=503,
        )

    verifier = secrets.token_urlsafe(48)
    state = secrets.token_urlsafe(24)
    params = urllib.parse.urlencode(
        {
            "client_id": client.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": jwtauth.sha256_b64(verifier.encode()),
            "code_challenge_method": "S256",
        }
    )
    response = RedirectResponse(f"/oauth/authorize?{params}", status_code=303)
    response.set_cookie(PKCE_COOKIE, verifier, max_age=600, **_cookie_flags())
    response.set_cookie(STATE_COOKIE, state, max_age=600, **_cookie_flags())
    return response


@router.get("/auth/callback")
async def auth_callback(request: Request):
    expected_state = request.cookies.get(STATE_COOKIE, "")
    got_state = request.query_params.get("state", "")
    code = request.query_params.get("code", "")
    if not expected_state or expected_state != got_state:
        return _error(
            request,
            "Sign-in failed",
            "The sign-in could not be verified (state mismatch). This usually means "
            "cookies are blocked, or too much time passed between starting sign-in and "
            "approving it. Allow cookies for this site and sign in again.",
        )
    if not code:
        return _error(request, "Sign-in failed", "No authorization code came back. Please try again.")
    try:
        claims = jwtauth.verify_auth_code(code)
    except Exception:
        return _error(
            request, "Sign-in expired", "That sign-in link is only valid for 5 minutes. Please sign in again."
        )

    try:
        client = ensure_web_client()
    except Exception:
        client = None
    if client is not None and claims.get("cid") != client.client_id:
        return _error(request, "Sign-in failed", "Authorization was issued for a different client.")

    sub = str(claims.get("sub", ""))
    if not sub:
        return _error(request, "Sign-in failed", "Sign-in did not identify a user. Please try again.")

    response = RedirectResponse("/app", status_code=303)
    response.set_cookie(
        SESSION_COOKIE, jwtauth.mint_access_token(sub), max_age=SESSION_MAX_AGE, **_cookie_flags()
    )
    response.delete_cookie(PKCE_COOKIE, path="/")
    response.delete_cookie(STATE_COOKIE, path="/")
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


# ----------------------------------------------------------------- MCP setup


@router.get("/connect", response_class="text/html; charset=utf-8")
async def connect(request: Request):
    base = APP_BASE_URL
    config = base64.b64encode(f'{{"type":"http","url":"{base}/mcp"}}'.encode()).decode()
    cursor_link = (
        f"cursor://anysphere.cursor-deeplink/mcp/install?name=Revizo&config={urllib.parse.quote(config)}"
    )
    manual_json = json.dumps({"mcpServers": {"revizo": {"url": f"{base}/mcp"}}}, indent=2)
    return templates.TemplateResponse(
        request,
        "connect.html",
        {
            "base": base,
            "mcp_url": f"{base}/mcp",
            "cursor_link": cursor_link,
            "manual_json": manual_json,
            "provider": os.getenv("SUPABASE_OAUTH_PROVIDER", "google"),
            "oauth_ready": bool(SUPABASE_URL and SUPABASE_ANON_KEY),
        },
    )


# ------------------------------------------------------------------- dashboard


@router.get("/app", response_class="text/html; charset=utf-8")
async def dashboard(request: Request, user: UserContext = Depends(require_user)):
    today = date.today()
    filters = {
        "difficulty": request.query_params.get("difficulty") or "",
        "status": request.query_params.get("status") or "",
        "topic": (request.query_params.get("topic") or "").strip(),
    }

    try:
        with SessionLocal() as session:
            data = service.dashboard_data(session, user.id, today=today)
    except Exception as e:
        logger.warning("dashboard load failed: %s", e)
        return _error(
            request,
            "Dashboard unavailable",
            "Could not load your data right now. Please refresh in a moment.",
            status=503,
        )

    problems = data["problems"]
    stats = data["stats"]
    due_problems = data["due_problems"]
    weak = data["weak"]
    history_map = data["history"]

    def visible(p) -> bool:
        if filters["difficulty"] and p.difficulty != filters["difficulty"]:
            return False
        if filters["topic"] and not any(
            filters["topic"].lower() == t.lower() for t in (p.topics or [])
        ):
            return False
        if filters["status"] == "solved" and not p.solved:
            return False
        if filters["status"] == "backlog" and p.solved:
            return False
        if filters["status"] == "due" and not is_due(p.last_solved, p.interval_days, p.solved, today):
            return False
        return True

    rows = [
        {
            "p": p,
            "due": is_due(p.last_solved, p.interval_days, p.solved, today),
            "history": history_map.get(p.id, []),
        }
        for p in problems
        if visible(p)
    ]

    due_cards = []
    for p in due_problems:
        days = overdue_days(p.last_solved, p.interval_days, today)
        due_cards.append(
            {
                "p": p,
                "watch_out": data["watch_outs"].get(p.id),
                "when": "never attempted" if p.last_solved is None else (f"{days}d overdue" if days else "due today"),
            }
        )

    max_count = max((v["count"] for v in weak.values()), default=0) or 1
    weak_points = [
        {"tag": tag, **data, "pct": round(data["count"] / max_count * 100)}
        for tag, data in weak.items()
    ]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "stats": stats,
            "due": due_cards,
            "weak_points": weak_points,
            "rows": rows,
            "filters": filters,
            "today_long": today.strftime("%A, %B %d"),
        },
    )


# ----------------------------------------------------------------- add problem


@router.get("/app/problems/new", response_class="text/html; charset=utf-8")
async def new_problem(request: Request, user: UserContext = Depends(require_user)):
    return templates.TemplateResponse(request, "new_problem.html", {"error": None, "form": {}})


@router.post("/app/problems/new")
async def create_problem(request: Request, user: UserContext = Depends(require_user)):
    form = await request.form()
    values = {
        "title": (form.get("title") or "").strip(),
        "link": (form.get("link") or "").strip(),
        "difficulty": (form.get("difficulty") or "medium").strip(),
        "topics": (form.get("topics") or "").strip(),
        "description": (form.get("description") or "").strip(),
    }

    def rerender(error: str, status: int = 400):
        return templates.TemplateResponse(
            request, "new_problem.html", {"error": error, "form": values}, status_code=status
        )

    if not values["title"]:
        return rerender("Give the problem a title.")

    topics = [t.strip() for t in values["topics"].split(",") if t.strip()]
    try:
        with SessionLocal() as session:
            try:
                service.add_problem(
                    session,
                    user.id,
                    problem_id=values["title"],
                    problem_link=values["link"],
                    difficulty=values["difficulty"],
                    problem_description=values["description"],
                    topics=topics,
                )
                session.commit()
            except ValueError as e:
                return rerender(str(e) or "That problem is already being tracked.")
        return RedirectResponse("/app", status_code=303)
    except Exception as e:
        logger.warning("add problem failed: %s", e)
        return rerender(
            "Something went wrong saving the problem. Please try again.", status_code=500
        )
