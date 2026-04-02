from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, Response, status

from web.config import WebSettings

_SESSION_COOKIE = "web_admin_session"


def _sign_token(token: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{token}.{digest}"


def _verify_signed(signed: str, secret: str) -> bool:
    if "." not in signed:
        return False
    token, got = signed.rsplit(".", 1)
    expected = hmac.new(secret.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(got, expected)


def create_session(response: Response, settings: WebSettings) -> None:
    raw_token = secrets.token_urlsafe(32)
    signed = _sign_token(raw_token, settings.session_secret)
    response.set_cookie(
        key=_SESSION_COOKIE,
        value=signed,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 12,
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(_SESSION_COOKIE)


def _is_authenticated(request: Request) -> bool:
    settings: WebSettings = request.app.state.settings
    signed = request.cookies.get(_SESSION_COOKIE)
    return bool(signed and _verify_signed(signed, settings.session_secret))


def require_page_auth(request: Request) -> None:
    if not _is_authenticated(request):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})


def require_api_auth(
    request: Request,
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    settings: WebSettings = request.app.state.settings
    if x_admin_key and hmac.compare_digest(x_admin_key, settings.admin_key):
        return
    if _is_authenticated(request):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


PageAuth = Annotated[None, Depends(require_page_auth)]
ApiAuth = Annotated[None, Depends(require_api_auth)]
