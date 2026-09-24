"""Self-minted HS256 tokens for MCP OAuth clients.

Authorization codes, access tokens and refresh tokens are all JWTs so the
OAuth flow stays stateless (serverless-friendly). No DB storage is needed
for them; `oauth_clients` stores dynamic client registrations.
"""

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

APP_SECRET_FILE = os.path.join(os.path.dirname(__file__), "..", ".app_secret")

access_token_seconds = 60 * 24 * 30
refresh_token_seconds = 60 * 60 * 24 * 365
auth_code_seconds = 300


def _load_secret() -> str:
    secret = os.getenv("APP_SECRET", "").strip()
    if secret:
        return secret
    path = os.path.abspath(APP_SECRET_FILE)
    if os.path.exists(path):
        secret = open(path).read().strip()
        if secret:
            return secret
    secret = uuid.uuid4().hex
    with open(path, "w") as f:
        f.write(secret)
    return secret


def _secret() -> str:
    return _load_secret()


def _encode(payload: dict, ttl: int) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {"iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex}
    claims.update({k: v for k, v in payload.items() if v is not None})
    return jwt.encode(claims, _secret(), algorithm="HS256")


def _decode(token: str, expected_typ: str) -> dict:
    claims = jwt.decode(token, _secret(), algorithms=["HS256"])
    if claims.get("typ") != expected_typ:
        raise jwt.InvalidTokenError(f"expected {expected_typ} token")
    return claims


def mint_auth_code(*, sub: str, client_id: str, redirect_uri: str, code_challenge: str) -> str:
    return _encode(
        {
            "typ": "auth_code",
            "sub": sub,
            "cid": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
        },
        auth_code_seconds,
    )


def verify_auth_code(code: str) -> dict:
    return _decode(code, "auth_code")


def sha256_b64(payload: bytes) -> str:
    digest = hashlib.sha256(payload).digest()
    import base64

    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    return code_challenge == sha256_b64(code_verifier.encode())


def mint_access_token(sub: str) -> str:
    return _encode({"typ": "access", "sub": sub}, access_token_seconds)


def mint_refresh_token(sub: str, client_id: str) -> str:
    return _encode({"typ": "refresh", "sub": sub, "cid": client_id}, refresh_token_seconds)


def verify_access_token(token: str) -> dict:
    return _decode(token, "access")


def verify_refresh_token(token: str) -> dict:
    return _decode(token, "refresh")
