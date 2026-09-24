"""ASGI middleware enforcing Bearer-token auth on the MCP endpoint.

Returns 401 with RFC 9728 WWW-Authenticate metadata so MCP clients
(Cursor, ChatGPT connectors, Claude) automatically discover the OAuth server.
"""

import json

from app import jwtauth

PROTECTED_PATHS = ("/mcp",)


class MCPAuthMiddleware:
    def __init__(self, app, fallback_base: str = "http://localhost:8000"):
        self.app = app
        self.fallback_base = fallback_base

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").rstrip("/") in PROTECTED_PATHS:
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            host = headers.get("host", "localhost:8000")
            scheme = headers.get("x-forwarded-proto", "http")
            metadata_url = f"http{'s' if scheme == 'https' else ''}://{host}/.well-known/oauth-protected-resource"
            token = headers.get("authorization", "")
            ok = False
            if token.lower().startswith("bearer "):
                try:
                    jwtauth.verify_access_token(token[7:].strip())
                    ok = True
                except Exception:
                    ok = False
            if not ok:
                body = json.dumps(
                    {
                        "error": "invalid_token",
                        "error_description": "valid Bearer token required - connect via OAuth",
                    }
                ).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (
                                b"www-authenticate",
                                f'Bearer resource_metadata="{metadata_url}"'.encode(),
                            ),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)
