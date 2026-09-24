import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from app.database import init_db
from app.mcp_server import mcp

logger = logging.getLogger("learnersmcp")
logging.basicConfig(level=logging.INFO)

# Public deployment: the SDK's default DNS-rebinding protection only allows
# localhost hosts/origins, which would reject every external client
# (Cursor pointed at the deployed URL, Cloudflare proxy headers, etc.).
mcp_app = mcp.streamable_http_app(
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
)


@asynccontextmanager
async def lifespan(app):
    try:
        init_db()
        logger.info("Database ready")
    except Exception as e:
        logger.warning("Database not reachable at startup: %s", e)
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan, title="learnersMcp API")


@app.get("/")
async def root():
    return {"message": "Hello from learnersMcp!"}


@app.get("/health")
async def health():
    return {"status": "ok"}


# Mount last so the API routes above keep matching.
# The MCP endpoint is served at exact path /mcp (Streamable HTTP).
app.mount("/", mcp_app)
