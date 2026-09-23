from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    name="learnersMcp",
    title="learnersMcp Tools",
    description="MCP tools served by learnersMcp. Deployment target: public, usable by all LLM clients.",
    version="0.1.0",
)


@mcp.tool()
def current_time() -> str:
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


@mcp.tool()
def todo_placeholder() -> str:
    """Placeholder tool. Replace with real tools as they are decided."""
    return "TODO: this placeholder tool awaits a real implementation."
