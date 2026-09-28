import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from mcp.server.transport_security import TransportSecuritySettings

from app.authz import MCPAuthMiddleware
from app.database import init_db
from app.mcp_server import mcp
from app.oauth_server import (
    APP_BASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
    ensure_web_client,
    router,
)
from app.web.deps import NotAuthenticated
from app.web.routes import router as web_router

load_dotenv()

logger = logging.getLogger("learnersmcp")
logging.basicConfig(level=logging.INFO)

# Stateless mode (no GET SSE stream, no sessions) is required on serverless
# hosts; locally Cursor expects the stateful contract, so default to stateful.
STATELESS = (os.getenv("MCP_STATELESS") or "0").strip() == "1"

mcp_app = mcp.streamable_http_app(
    stateless_http=STATELESS,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

# Metadata URLs are computed per-request from the Host header so localhost and
# 127.0.0.1 (and the deployed domain) each self-match.
PROTECTED = MCPAuthMiddleware(mcp_app, fallback_base=APP_BASE_URL)

oauth_ready = bool(SUPABASE_URL and SUPABASE_ANON_KEY)


@asynccontextmanager
async def lifespan(app):
    try:
        init_db()
        ensure_web_client()  # register the web dashboard as an OAuth client of ourselves
        logger.info("Database ready")
    except Exception as e:
        logger.warning("Database not reachable at startup: %s", e)
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan, title="Revizo API")


@app.get("/health")
async def health():
    return {"status": "ok", "oauth": "configured" if oauth_ready else "not-configured"}


LOGO_PATH = Path(__file__).parent / "public" / "revizo.png"

MARK_PATH = Path(__file__).parent / "public" / "mark.svg"

APP_CSS_PATH = Path(__file__).parent / "public" / "app.css"

# Static brand/build assets: effectively immutable — bump the query string in
# templates if one ever changes.
CACHE_IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


def _logo() -> FileResponse:
    return FileResponse(LOGO_PATH, media_type="image/png", headers=CACHE_IMMUTABLE)


@app.get("/logo")
async def logo():
    return _logo()


@app.get("/mark.svg")
async def mark_svg():
    return FileResponse(MARK_PATH, media_type="image/svg+xml", headers=CACHE_IMMUTABLE)


@app.get("/app.css")
async def app_css():
    # safe to cache forever: the ?v=<hash> in the template link busts on rebuild
    return FileResponse(APP_CSS_PATH, media_type="text/css", headers=CACHE_IMMUTABLE)


# OAuth endpoints under /oauth + well-known metadata
from app.oauth_server import router as oauth_router  # noqa: E402

app.include_router(oauth_router)

# Web dashboard: cookie-session pages. Registered as its own exception handler
# so anonymous page hits become a 303 redirect to /login.
app.include_router(web_router)


@app.exception_handler(NotAuthenticated)
async def _redirect_to_login(request, exc: NotAuthenticated):
    return RedirectResponse("/login", status_code=303)


# MCP only reachable WITH a valid Bearer token (401 otherwise).
# Mount last so the routes above keep matching.
app.mount("/", PROTECTED)
