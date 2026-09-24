import base64
import logging
import os
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from mcp.server.transport_security import TransportSecuritySettings

from app.authz import MCPAuthMiddleware
from app.database import init_db
from app.mcp_server import mcp
from app.oauth_server import APP_BASE_URL, SUPABASE_URL, SUPABASE_ANON_KEY, router

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
        logger.info("Database ready")
    except Exception as e:
        logger.warning("Database not reachable at startup: %s", e)
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan, title="Revizo API")


@app.get("/")
async def root():
    return {"message": "Revizo is up."}


@app.get("/health")
async def health():
    return {"status": "ok", "oauth": "configured" if oauth_ready else "not-configured"}


@app.get("/logo")
async def logo():
    return _logo()


LOGO_PATH = Path(__file__).parent / "revizo.png"


def _logo() -> FileResponse:
    return FileResponse(LOGO_PATH, media_type="image/png")


@app.get("/connect", response_class=HTMLResponse)
async def connect():
    base = APP_BASE_URL
    if not oauth_ready:
        return HTMLResponse(
            "<h1>Revizo</h1>"
            '<img src="/logo" alt="Revizo" style="max-width:420px;border-radius:12px"/>'
            "<p>OAuth is not configured yet. Set SUPABASE_URL and "
            "SUPABASE_ANON_KEY in the environment and enable a Sign-in provider in Supabase.</p>"
        )
    raw_config = f'{{"type":"http","url":"{base}/mcp"}}'
    config = base64.b64encode(raw_config.encode()).decode()
    cursor_link = (
        f"cursor://anysphere.cursor-deeplink/mcp/install?name=Revizo&config={urllib.parse.quote(config)}"
    )
    html = f"""
    <div style="font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;color:#eaeaea;background:#0d1117;padding:32px;border-radius:16px">
        <img src="/logo" alt="Revizo" style="max-width:420px;border-radius:12px"/>
        <p style="font-size:15px;color:#b9b9c6"><em>Your problems remember what you got wrong.</em></p>
        <p style="color:#eaeaea">All you need is the <b>Add to Cursor</b> button - on first connect Cursor opens a
        browser sign-in ({os.getenv('SUPABASE_OAUTH_PROVIDER', 'google')}). No settings editing needed.</p>
        <p><a href="{cursor_link}"><button style="padding:12px 20px;font-size:16px;border-radius:8px;cursor:pointer">Add to Cursor</button></a></p>
        <p style="color:#9a9aa8">Manual fallback (any other MCP client): URL is <code>{base}/mcp</code> - OAuth flow starts automatically.</p>
    </div>
    """
    return HTMLResponse(html)


# OAuth endpoints under /oauth + well-known metadata
from app.oauth_server import router as oauth_router  # noqa: E402

app.include_router(oauth_router)

# MCP only reachable WITH a valid Bearer token (401 otherwise).
# Mount last so the routes above keep matching.
app.mount("/", PROTECTED)
