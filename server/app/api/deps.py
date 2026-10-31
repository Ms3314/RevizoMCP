"""Auth dependency for the JSON API.

Reuses the cookie-session resolver from app.web.deps but returns 401 (JSON)
instead of raising NotAuthenticated (which the page router turns into a 303
redirect to /login). The SPA handles 401 by sending the visitor to /login.
"""

from fastapi import HTTPException, Request

from app.web.deps import UserContext, get_current_user


def get_api_user(request: Request) -> UserContext:
    user = get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
