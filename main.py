from contextlib import asynccontextmanager

from fastapi import FastAPI

from mcp_server import mcp

mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app):
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
