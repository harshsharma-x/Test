"""Request authentication for the Zepto-compatible API layer.

A session is carried either as `Authorization: Bearer <token>` (what the web
client uses) or as the `zepto_session` cookie set by verify-otp.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.authentication import AuthenticationService
from backend.database.connection import get_db
from backend.database.models import AuthSession, ShoppingAccount, User

SESSION_COOKIE_NAME = "zepto_session"
UNAUTHORIZED_DETAIL = "Authentication required. Verify your mobile number to continue."


@dataclass
class AuthContext:
    """The authenticated caller plus the shopping account currently in use."""

    session: AuthSession
    user: User
    account: ShoppingAccount
    token: str

    @property
    def account_id(self) -> str:
        return self.account.id


def extract_token(
    authorization: Optional[str] = None,
    cookie_token: Optional[str] = None,
) -> Optional[str]:
    """Pulls a bearer token from the Authorization header, then the cookie."""
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            return value.strip()
        if not _ and authorization.strip():
            return authorization.strip()
    if cookie_token:
        return cookie_token.strip()
    return None


def optional_auth(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    zepto_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> Optional[AuthContext]:
    """Returns the auth context when a valid session is present, else None."""
    token = extract_token(authorization, zepto_session)
    if not token:
        return None
    resolved = AuthenticationService.resolve_session(db, token)
    if not resolved:
        return None
    session, user, account = resolved
    return AuthContext(session=session, user=user, account=account, token=token)


def require_auth(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    zepto_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
) -> AuthContext:
    """Like optional_auth but rejects unauthenticated callers with 401."""
    token = extract_token(authorization, zepto_session)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_DETAIL)

    resolved = AuthenticationService.resolve_session(db, token)
    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please sign in again.",
        )

    session, user, account = resolved
    return AuthContext(session=session, user=user, account=account, token=token)
