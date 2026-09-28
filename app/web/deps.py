"""Cookie-session auth for web dashboard pages.

The session cookie carries the same self-minted access JWT that MCP clients
get from /oauth/token, so `sub` resolves to the same users row. Pages declare
`user: UserContext = Depends(require_user)`; an anonymous hit raises
NotAuthenticated, which main.py turns into a 303 redirect to /login.
"""

import logging
from dataclasses import dataclass

from fastapi import Request

from app import jwtauth
from app.database import SessionLocal
from app.models import User

logger = logging.getLogger("learnersmcp")

SESSION_COOKIE = "lr_session"


@dataclass
class UserContext:
    id: int
    email: str
    display_name: str


class NotAuthenticated(Exception):
    """Raised when a page requires a signed-in user."""


def get_current_user(request: Request) -> UserContext | None:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        return None
    try:
        claims = jwtauth.verify_access_token(token)
    except Exception:
        return None
    try:
        user_id = int(str(claims.get("sub", "")))
    except ValueError:
        return None
    try:
        with SessionLocal() as session:
            user = session.get(User, user_id)
            if user is None:
                return None
            return UserContext(
                id=user.id,
                email=user.email,
                display_name=user.display_name or user.email.split("@")[0],
            )
    except Exception as e:
        logger.warning("web session lookup failed: %s", e)
        return None


def require_user(request: Request) -> UserContext:
    user = get_current_user(request)
    if user is None:
        raise NotAuthenticated()
    return user
