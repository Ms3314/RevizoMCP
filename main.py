import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import db
from mcp_server import mcp

logger = logging.getLogger("learnersmcp")
logging.basicConfig(level=logging.INFO)

mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app):
    try:
        db.init_db()
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
