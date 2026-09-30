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
from app.secret_storage import (
    SecretStorageError,
    encrypt_leetcode_session,
)
from app.oauth_server import (
    APP_BASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
    _issuer_from_request,
    ensure_web_client,
)
from app.models import User
from app.srs import is_due, overdue_days
from app.web.csv_import import MAX_FILE_BYTES, parse_csv
from app.web.deps import (
    SESSION_COOKIE,
    UserContext,
    get_current_user,
    require_user,
)

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


# ----------------------------------------------------------------- docs (public)


def _docs_user(request: Request):
    return get_current_user(request)


@router.get("/docs", response_class="text/html; charset=utf-8")
async def docs_index(request: Request, user: UserContext | None = Depends(_docs_user)):
    return templates.TemplateResponse(
        request,
        "docs_index.html",
        {
            "user": user,
            "doc": {"title": "Docs", "prev": None, "next": {"href": "/docs/introduction", "title": "About Revizo"}},
        },
    )


def _connect_vars(request: Request) -> dict:
    # Show the URL of the server the browser is actually on (Host header +
    # forwarded proto), not APP_BASE_URL — localhost vs 127.0.0.1 vs a deploy
    # domain each get their own correct URL in the docs.
    base = _issuer_from_request(request)
    config = base64.b64encode(f'{{"type":"http","url":"{base}/mcp"}}'.encode()).decode()
    return {
        "mcp_url": f"{base}/mcp",
        "cursor_link": (
            "cursor://anysphere.cursor-deeplink/mcp/install?name=Revizo"
            f"&config={urllib.parse.quote(config)}"
        ),
        "manual_json": json.dumps({"mcpServers": {"revizo": {"url": f"{base}/mcp"}}}, indent=2),
        "provider": os.getenv("SUPABASE_OAUTH_PROVIDER", "google"),
        "oauth_ready": bool(SUPABASE_URL and SUPABASE_ANON_KEY),
    }


DOCS_PAGES = {
    "introduction": {"title": "About Revizo", "template": "introduction.html"},
    "features": {"title": "Features", "template": "features.html"},
    "leetcode-import": {"title": "LeetCode import", "template": "leetcode_import.html"},
    "importing": {"title": "Importing problems", "template": "importing.html"},
    "connect": {"title": "Connect Revizo", "template": "connect_overview.html"},
    "connect/cursor": {"title": "Cursor", "template": "connect_cursor.html"},
    "connect/claude": {"title": "Claude Desktop", "template": "connect_claude.html"},
    "connect/claude-code": {"title": "Claude Code", "template": "connect_claude_code.html"},
    "connect/chatgpt": {"title": "ChatGPT", "template": "connect_chatgpt.html"},
    "connect/codex": {"title": "Codex", "template": "connect_coming_soon.html", "client": "Codex"},
    "connect/hermes": {"title": "Hermes", "template": "connect_coming_soon.html", "client": "Hermes"},
    "connect/other": {"title": "Other MCP clients", "template": "connect_other.html"},
}
DOCS_ORDER = list(DOCS_PAGES)


def _docs_page(request: Request, user, key: str):
    meta = DOCS_PAGES[key]
    idx = DOCS_ORDER.index(key)
    prev_key = DOCS_ORDER[idx - 1] if idx > 0 else None
    next_key = DOCS_ORDER[idx + 1] if idx + 1 < len(DOCS_ORDER) else None
    ctx = {
        "user": user,
        "doc": {
            "title": meta["title"],
            "prev": {"href": f"/docs/{prev_key}", "title": DOCS_PAGES[prev_key]["title"]} if prev_key else None,
            "next": {"href": f"/docs/{next_key}", "title": DOCS_PAGES[next_key]["title"]} if next_key else None,
        },
    }
    if "client" in meta:
        ctx["client_name"] = meta["client"]
    if key.startswith("connect"):
        ctx.update(_connect_vars(request))
    return templates.TemplateResponse(request, meta["template"], ctx)


@router.get("/docs/introduction")
async def docs_introduction(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "introduction")


@router.get("/docs/features")
async def docs_features(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "features")


@router.get("/docs/leetcode-import")
async def docs_leetcode_import(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "leetcode-import")


@router.get("/docs/importing")
async def docs_importing(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "importing")


@router.get("/docs/connect")
async def docs_connect(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "connect")


@router.get("/docs/connect/cursor")
async def docs_connect_cursor(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "connect/cursor")


@router.get("/docs/connect/claude")
async def docs_connect_claude(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "connect/claude")


@router.get("/docs/connect/claude-code")
async def docs_connect_claude_code(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "connect/claude-code")


@router.get("/docs/connect/chatgpt")
async def docs_connect_chatgpt(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "connect/chatgpt")


@router.get("/docs/connect/codex")
async def docs_connect_codex(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "connect/codex")


@router.get("/docs/connect/hermes")
async def docs_connect_hermes(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "connect/hermes")


@router.get("/docs/connect/other")
async def docs_connect_other(request: Request, user: UserContext | None = Depends(_docs_user)):
    return _docs_page(request, user, "connect/other")


@router.get("/connect")
async def connect_redirect():
    # README references /connect; docs now live under /docs
    return RedirectResponse("/docs/connect", status_code=308)


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


def _leetcode_settings_page(
    request: Request,
    user: UserContext,
    *,
    connected: bool,
    username: str = "",
    error: str | None = None,
    notice: str | None = None,
    result: dict | None = None,
    status_code: int = 200,
):
    response = templates.TemplateResponse(
        request,
        "leetcode_settings.html",
        {
            "user": user,
            "connected": connected,
            "username": username,
            "error": error,
            "notice": notice,
            "result": result,
        },
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/app/leetcode", response_class="text/html; charset=utf-8")
async def leetcode_settings(request: Request, user: UserContext = Depends(require_user)):
    with SessionLocal() as session:
        account = session.get(User, user.id)
        connected = bool(account and account.leetcode_session)
        username = (account.leetcode_username or "") if account else ""
    return _leetcode_settings_page(
        request,
        user,
        connected=connected,
        username=username,
        notice=request.query_params.get("saved"),
    )


@router.post("/app/leetcode/settings")
async def save_leetcode_settings(request: Request, user: UserContext = Depends(require_user)):
    from app.leetcode_sync import normalize_session_cookie

    form = await request.form()
    username = (form.get("username") or "").strip()
    raw_cookie = (form.get("session_cookie") or "").strip()
    if not username:
        with SessionLocal() as session:
            account = session.get(User, user.id)
            connected = bool(account and account.leetcode_session)
        return _leetcode_settings_page(
            request, user, connected=connected, username=username,
            error="Enter your LeetCode username.", status_code=400,
        )
    try:
        encrypted_cookie = (
            encrypt_leetcode_session(normalize_session_cookie(raw_cookie))
            if raw_cookie
            else None
        )
    except ValueError as e:
        return _leetcode_settings_page(
            request,
            user,
            connected=False,
            username=username,
            error=str(e),
            status_code=400,
        )
    except SecretStorageError as e:
        with SessionLocal() as session:
            account = session.get(User, user.id)
            connected = bool(account and account.leetcode_session)
        return _leetcode_settings_page(
            request,
            user,
            connected=connected,
            username=username,
            error=str(e),
            status_code=503,
        )

    with SessionLocal() as session:
        account = session.get(User, user.id)
        if account is None:
            return _leetcode_settings_page(
                request, user, connected=False, username=username,
                error="Your account could not be found. Please sign in again.", status_code=404,
            )
        account.leetcode_username = username
        if encrypted_cookie is not None:
            account.leetcode_session = encrypted_cookie
        connected = bool(account.leetcode_session)
        session.commit()

    return _leetcode_settings_page(
        request,
        user,
        connected=connected,
        username=username,
        notice="LeetCode settings saved.",
    )


@router.post("/app/leetcode/disconnect")
async def disconnect_leetcode(request: Request, user: UserContext = Depends(require_user)):
    username = ""
    with SessionLocal() as session:
        account = session.get(User, user.id)
        if account is not None:
            account.leetcode_session = ""
            session.commit()
            username = account.leetcode_username or ""
    return _leetcode_settings_page(
        request,
        user,
        connected=False,
        username=username,
        notice="LeetCode session removed.",
    )


@router.post("/app/leetcode/import")
async def import_all_leetcode_page(request: Request, user: UserContext = Depends(require_user)):
    from app.leetcode_sync import import_all_solved
    from app.secret_storage import decrypt_leetcode_session

    with SessionLocal() as session:
        account = session.get(User, user.id)
        username = (account.leetcode_username or "").strip() if account else ""
        encrypted_cookie = account.leetcode_session if account else ""
    connected = bool(encrypted_cookie)
    try:
        session_cookie = decrypt_leetcode_session(encrypted_cookie)
        if not username or not session_cookie:
            return _leetcode_settings_page(
                request,
                user,
                connected=connected,
                username=username,
                error="Add your LeetCode username and session cookie before importing.",
                status_code=400,
            )
        result = import_all_solved(
            username=username, session_cookie=session_cookie, user_id=user.id
        )
    except (RuntimeError, SecretStorageError, ValueError) as e:
        return _leetcode_settings_page(
            request,
            user,
            connected=connected,
            username=username,
            error=str(e),
            status_code=400,
        )
    return _leetcode_settings_page(
        request,
        user,
        connected=True,
        username=username,
        result=result,
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


# ----------------------------------------------------------------- csv import


@router.get("/app/import", response_class="text/html; charset=utf-8")
async def import_problems_page(request: Request, user: UserContext = Depends(require_user)):
    return templates.TemplateResponse(request, "import_problems.html", {"result": None, "error": None})


@router.get("/import/sample.csv")
async def import_sample_csv():
    """Downloadable template so users can fill in a correct CSV directly."""
    from fastapi.responses import Response

    content = (
        "Problem,Link,Difficulty,Topics,Description\n"
        "Two Sum,https://leetcode.com/problems/two-sum/,easy,\"arrays, hashing\",Find two numbers adding up to the target.\n"
        "Coin Change,https://leetcode.com/problems/coin-change/,medium,dp,Fewest coins to make up an amount.\n"
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="revizo_import_template.csv"'},
    )


@router.post("/app/import")
async def import_problems(request: Request, user: UserContext = Depends(require_user)):
    from fastapi.responses import StreamingResponse

    form = await request.form()
    upload = form.get("file")

    if upload is None or not getattr(upload, "filename", ""):
        return templates.TemplateResponse(
            request, "import_problems.html",
            {"result": None, "error": "Choose a .csv file to upload."}, status_code=400,
        )
    if not upload.filename.lower().endswith(".csv"):
        return templates.TemplateResponse(
            request, "import_problems.html",
            {"result": None, "error": "Only .csv files are supported."}, status_code=400,
        )

    data = await upload.read()
    if len(data) > MAX_FILE_BYTES:
        return templates.TemplateResponse(
            request, "import_problems.html",
            {"result": None, "error": "File is too large — keep it under 1 MB."}, status_code=400,
        )

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return templates.TemplateResponse(
            request, "import_problems.html",
            {"result": None, "error": "That file isn't valid UTF-8 text — re-save it as a plain CSV."}, status_code=400,
        )

    try:
        parsed = parse_csv(text)
    except ValueError as e:
        return templates.TemplateResponse(
            request, "import_problems.html",
            {"result": None, "error": str(e)}, status_code=400,
        )

    if not parsed.rows:
        return templates.TemplateResponse(
            request, "import_problems.html",
            {"result": None, "error": "No importable problems found — every row needs both a problem and a link."}, status_code=400,
        )

    async def event_stream():
        imported, duplicates, failed = 0, 0, []
        total = len(parsed.rows)

        # Initial event: total rows to process
        yield f"data: {json.dumps({'type': 'start', 'total': total, 'skipped': len(parsed.skipped)})}\n\n"

        try:
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

                    # Stream progress every 10 rows or at the end
                    if (i + 1) % 10 == 0 or i == total - 1:
                        yield f"data: {json.dumps({'type': 'progress', 'processed': i + 1, 'total': total, 'imported': imported, 'duplicates': duplicates})}\n\n"

                session.commit()
        except Exception as e:
            logger.warning("csv import failed: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Something went wrong importing.'})}\n\n"
            return

        # Final event with full summary
        summary = {
            'type': 'done',
            'imported': imported,
            'duplicates': duplicates,
            'skipped': [{'row_number': s.row_number, 'reason': s.reason} for s in parsed.skipped],
            'extras_ignored': parsed.extras_ignored,
            'too_many_rows': parsed.too_many_rows,
            'failed': failed,
        }
        yield f"data: {json.dumps(summary)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
