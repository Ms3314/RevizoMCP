"""MCP-spec OAuth authorization server bridged to Supabase Auth.

Flow: client POSTs /oauth/register (DCR), browser opens /oauth/authorize,
we redirect to Supabase Auth (provider via PKCE), Supabase redirects back to
/oauth/callback, we exchange the Supabase code, upsert the users row and
redirect to the client's redirect_uri with a short-lived stateless auth code
JWT. The client exchanges it (code + PKCE verifier) at /oauth/token for an
access JWT.

Stateless by design: the PKCE verifier travels in a signed cookie and the
client's redirect parameters travel inside the auth code JWT itself.
"""

import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from dotenv import load_dotenv
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import insert, select

from app import jwtauth
from app.database import SessionLocal, engine
from app.models import OAuthClient, User

load_dotenv()

APP_BASE_URL = (os.getenv("APP_BASE_URL") or "http://localhost:8000").strip().rstrip("/")
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_ANON_KEY = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
SUPABASE_PROVIDER = (os.getenv("SUPABASE_OAUTH_PROVIDER") or "google").strip()

MCP_SCOPE = "mcp"

router = APIRouter()


class OAuthConfigError(RuntimeError):
    pass


def _require_supabase_config() -> None:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise OAuthConfigError(
            "OAuth is not configured: set SUPABASE_URL and SUPABASE_ANON_KEY in .env "
            "and enable a Sign-in provider in your Supabase project"
        )


def _issuer_from_request(request: Request) -> str:
    """Issuer matches the origin the client actually calls, so localhost /
    127.0.0.1 / the deployed domain all self-consistently match."""
    from urllib.parse import urlsplit

    host = request.headers.get("host") or urlsplit(APP_BASE_URL).netloc
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{scheme}://{host}"


def resource_metadata(request: Request) -> dict:
    issuer = _issuer_from_request(request)
    return {
        "resource": f"{issuer}/mcp",
        "resource_documentation": issuer,
        "authorization_servers": [issuer],
    }


def authorization_server_metadata(request: Request) -> dict:
    issuer = _issuer_from_request(request)
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/oauth/authorize",
        "token_endpoint": f"{issuer}/oauth/token",
        "registration_endpoint": f"{issuer}/oauth/register",
        "scopes_supported": [MCP_SCOPE],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
    }


def _get_client(client_id: str) -> OAuthClient | None:
    with SessionLocal() as session:
        client = session.get(OAuthClient, client_id)
        session.commit()
        return client


def _validate_redirect(client: OAuthClient | None, redirect_uri: str) -> None:
    if client is None:
        raise OAuthConfigError("unregistered client_id")
    base, _, _ = redirect_uri.partition("?")
    if base not in (client.redirect_uris or []):
        raise OAuthConfigError("redirect_uri not registered for this client")


@router.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata(request: Request):
    return JSONResponse(resource_metadata(request))


@router.get("/.well-known/oauth-authorization-server")
async def auth_server_metadata(request: Request):
    return JSONResponse(authorization_server_metadata(request))


@router.post("/oauth/register")
async def register_client(request: Request):
    body = await request.json()
    redirect_uris = body.get("redirect_uris") or []
    if not redirect_uris:
        return JSONResponse(
            {"error": "invalid_client_metadata", "error_description": "redirect_uris required"},
            status_code=400,
        )
    client_id = "cl_" + secrets.token_urlsafe(16)
    with engine.begin() as conn:
        conn.execute(
            insert(OAuthClient).values(
                client_id=client_id,
                redirect_uris=redirect_uris,
                client_name=(body.get("client_name") or "")[:80],
                created_at=date.today(),
            )
        )
    return JSONResponse(
        {
            "client_id": client_id,
            "client_name": body.get("client_name") or "",
            "redirect_uris": redirect_uris,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
        status_code=201,
    )


@router.get("/oauth/authorize")
async def authorize(request: Request):
    try:
        _require_supabase_config()
        params = dict(request.query_params)
        client_id = params.get("client_id", "")
        redirect_uri = params.get("redirect_uri", "")
        state = params.get("state", "")
        code_challenge = params.get("code_challenge", "")
        method = params.get("code_challenge_method", "S256")

        if not (client_id and redirect_uri and state and code_challenge and method == "S256"):
            return JSONResponse(
                {
                    "error": "invalid_request",
                    "error_description": "client_id, redirect_uri, state, code_challenge (S256) required",
                },
                status_code=400,
            )
        _validate_redirect(_get_client(client_id), redirect_uri)
    except OAuthConfigError as e:
        return JSONResponse({"error": "unauthorized_client", "error_description": str(e)}, status_code=400)

    verifier = secrets.token_urlsafe(48)
    bridge = jwtauth._encode(
        {
            "typ": "bridge",
            "verifier": verifier,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
        },
        600,
    )

    query = urllib.parse.urlencode(
        {
            "provider": SUPABASE_PROVIDER,
            "redirect_to": f"{_issuer_from_request(request)}/oauth/callback",
            "code_challenge": jwtauth.sha256_b64(verifier.encode()),
            "code_challenge_method": "S256",
            "apikey": SUPABASE_ANON_KEY,
        }
    )
    response = JSONResponse(
        {"detail": "redirecting to sign-in"},
        status_code=302,
        headers={"Location": f"{SUPABASE_URL}/auth/v1/authorize?{query}"},
    )
    response.set_cookie("lr_bridge", bridge, max_age=600, samesite="lax", path="/oauth")
    return response


async def _exchange_supabase_code(auth_code: str, code_verifier: str) -> dict:
    _require_supabase_config()
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=pkce"
    req = urllib.request.Request(
        url,
        data=json.dumps({"auth_code": auth_code, "code_verifier": code_verifier}).encode(),
        headers={"Content-Type": "application/json", "apikey": SUPABASE_ANON_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise OAuthConfigError(
            f"Supabase code exchange failed: HTTP {e.code} {e.read().decode()[:200]}"
        ) from e


def _upsert_user(sub: str, email: str) -> int:
    with SessionLocal() as session:
        user = session.scalars(select(User).where(User.supabase_sub == sub)).first()
        if user is None:
            user = User(
                supabase_sub=sub,
                email=email,
                display_name=email.split("@")[0],
                created_at=date.today(),
            )
            session.add(user)
        else:
            user.email = email or user.email
        session.commit()
        session.refresh(user)
        return user.id


@router.get("/oauth/callback")
async def supabase_callback(request: Request):
    try:
        bridge = jwtauth._decode(request.cookies.get("lr_bridge", ""), "bridge")
    except Exception as e:
        return JSONResponse({"error": f"OAuth bridge invalid: {e}"}, status_code=400)

    auth_code = request.query_params.get("code", "")
    if not auth_code:
        return JSONResponse({"error": "no code from Supabase"}, status_code=400)

    try:
        supabase = await _exchange_supabase_code(auth_code, bridge["verifier"])
    except OAuthConfigError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    user_info = supabase.get("user") or {}
    sub = user_info.get("id") or ""
    email = user_info.get("email") or ""
    if not sub:
        return JSONResponse({"error": "Supabase returned no user id"}, status_code=400)

    user_id = _upsert_user(sub, email)

    code = jwtauth.mint_auth_code(
        sub=str(user_id),
        client_id=bridge["client_id"],
        redirect_uri=bridge["redirect_uri"],
        code_challenge=bridge["code_challenge"],
    )
    redirect = bridge["redirect_uri"]
    sep = "&" if "?" in redirect else "?"
    location = f"{redirect}{sep}code={urllib.parse.quote(code)}&state={urllib.parse.quote(bridge['state'])}"
    response = JSONResponse({"detail": "authorized"}, status_code=302, headers={"Location": location})
    response.delete_cookie("lr_bridge", path="/oauth")
    return response


@router.post("/oauth/token")
async def token(request: Request):
    form = await request.form()
    grant_type = form.get("grant_type", "")
    try:
        if grant_type == "authorization_code":
            return _token_from_authorization_code(form)
        if grant_type == "refresh_token":
            return _token_from_refresh(form.get("refresh_token", ""), form.get("client_id", ""))
        return JSONResponse(
            {"error": "unsupported_grant_type", "error_description": grant_type}, status_code=400
        )
    except OAuthConfigError as e:
        return JSONResponse({"error": "invalid_grant", "error_description": str(e)}, status_code=400)


def _token_from_authorization_code(form) -> JSONResponse:
    code = form.get("code", "")
    verifier = form.get("code_verifier", "")
    if not code or not verifier:
        raise OAuthConfigError("code and code_verifier required")
    claims = jwtauth.verify_auth_code(code)
    if not jwtauth.verify_pkce(verifier, claims.get("code_challenge", "")):
        raise OAuthConfigError("PKCE verification failed")
    if form.get("client_id", "") != claims.get("cid", ""):
        raise OAuthConfigError("client_id mismatch")
    redirect_uri = form.get("redirect_uri", "")
    if redirect_uri and redirect_uri != claims.get("redirect_uri"):
        raise OAuthConfigError("redirect_uri mismatch")

    sub = claims["sub"]
    access = jwtauth.mint_access_token(sub)
    refresh = jwtauth.mint_refresh_token(sub, claims["cid"])
    return JSONResponse(
        {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": jwtauth.access_token_seconds,
            "refresh_token": refresh,
            "scope": MCP_SCOPE,
        }
    )


def _token_from_refresh(refresh_token: str, client_id: str) -> JSONResponse:
    try:
        claims = jwtauth.verify_refresh_token(refresh_token)
    except Exception as e:
        raise OAuthConfigError(f"invalid refresh token: {e}") from e
    if client_id and client_id != claims.get("cid", ""):
        raise OAuthConfigError("client_id mismatch")
    access = jwtauth.mint_access_token(claims["sub"])
    return JSONResponse(
        {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": jwtauth.access_token_seconds,
            "scope": MCP_SCOPE,
        }
    )
