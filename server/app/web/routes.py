"""Web routes that remain server-rendered.

Login reuses the MCP-spec OAuth flow: the web app acts as just another OAuth
client of this server's own /oauth/* endpoints. /login generates PKCE + state,
/oauth/authorize bridges to Supabase (Google), /oauth/callback mints a
short-lived auth code JWT, and /auth/callback (web-only) turns that auth code
into an HttpOnly session cookie — no /oauth/token round-trip needed, since
/oauth/callback has already verified PKCE by the time it issues the code.

The dashboard, LeetCode and import pages were ported to the React SPA and are
now served by `app.api.routes` (JSON) + the SPA shell. Landing and the docs
tree stay Jinja until Phase 3.
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

from app import jwtauth
from app.oauth_server import (
    APP_BASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
    _issuer_from_request,
    ensure_web_client,
)
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
