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
from app.api.routes import router as api_router

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


app = FastAPI(
    lifespan=lifespan,
    title="Revizo API",
    docs_url="/api/docs",  # Swagger moved aside — /docs is the user-facing docs section
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.get("/health")
async def health():
    return {"status": "ok", "oauth": "configured" if oauth_ready else "not-configured"}


PUBLIC_DIR = Path(__file__).parent / "public"
# React build output (web/dist copied here by the build step). Served below via
# a SPA catch-all so the same origin hosts both the API/MCP and the dashboard.
# Kept separate from PUBLIC_DIR so committed brand assets (mark.svg, app.css, …)
# and generated SPA files don't mix, and the generated dir can be gitignored.
DIST_DIR = Path(__file__).parent / "static"

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

# JSON API consumed by the React SPA.
app.include_router(api_router, prefix="/api")


@app.exception_handler(NotAuthenticated)
async def _redirect_to_login(request, exc: NotAuthenticated):
    return RedirectResponse("/login", status_code=303)


# MCP only reachable WITH a valid Bearer token (401 otherwise).
# Mounted at "/" so the external endpoint stays exactly /mcp (the app's own
# streamable-http route). The SPA is layered on via SPAMiddleware below, which
# only activates once a build exists and only for migrated route prefixes, so
# the existing Jinja pages keep working until each section is ported.
app.mount("/", PROTECTED)


# ----------------------------------------------------------------- SPA middleware
# Serves the built React app (index.html + hashed assets) from DIST_DIR for
# client-side routes. It is inert until index.html exists, and only intercepts
# the route prefixes we've actually migrated — every other request falls through
# to the FastAPI routers above (MCP, OAuth, API, Jinja pages).
class SPAMiddleware:
    def __init__(self, app, dist_dir: Path, spa_prefixes: set[str]):
        self.app = app
        self.dist_dir = dist_dir
        self.spa_prefixes = spa_prefixes

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope["method"] in ("GET", "HEAD"):
            index = self.dist_dir / "index.html"
            if index.is_file():
                path = scope["path"]
                # A real built asset (hashed files under /assets, etc.).
                if path and not path.endswith("/"):
                    candidate = (self.dist_dir / path.lstrip("/")).resolve()
                    if candidate.is_file() and (
                        candidate == self.dist_dir or self.dist_dir in candidate.parents
                    ):
                        resp = FileResponse(
                            candidate,
                            headers=(
                                {"Cache-Control": "public, max-age=31536000, immutable"}
                                if path != "/index.html"
                                else {}
                            ),
                        )
                        await resp(scope, receive, send)
                        return
                # A migrated client-side route → serve the SPA shell.
                if any(path == p or path.startswith(p + "/") for p in self.spa_prefixes):
                    resp = FileResponse(index, media_type="text/html")
                    await resp(scope, receive, send)
                    return
        await self.app(scope, receive, send)


# Positive allow-list of routes owned by the React SPA. Grows as each section is
# ported: "/app" (dashboard/forms) → "/" (landing) → "/docs" (docs tree). The
# middleware matches exact "/", or path == p or path.startswith(p + "/") for the
# multi-segment prefixes, so "/login", "/oauth", "/mcp", "/api" and "/app.css"
# are never swallowed. Until index.html exists this middleware is a no-op.
# "/docs" stays OFF this list until the React docs tree is wired into the
# router — adding it early serves the SPA shell (and its 404) over the working
# Jinja docs pages.
SPA_PREFIXES = {"/app", "/"}

app.add_middleware(SPAMiddleware, dist_dir=DIST_DIR, spa_prefixes=SPA_PREFIXES)
