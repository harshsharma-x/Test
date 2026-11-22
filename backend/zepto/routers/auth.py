"""Authentication router.

Documented endpoints
    GET  /api/auth/create-csrf-token
    POST /api/v1/user/customer/send-otp-sms/
    POST /api/auth/verify-otp

Supporting endpoints used by the web client
    GET  /api/auth/session        - current user + linked accounts
    POST /api/auth/switch-account - change active shopping account
    POST /api/auth/logout         - revoke the bearer session
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.accounts.manager import MultiAccountManager
from backend.api.authentication import AuthenticationService
from backend.database.connection import get_db
from backend.database.crypto import decrypt_data
from backend.zepto.deps import SESSION_COOKIE_NAME, AuthContext, require_auth

router = APIRouter(tags=["Authentication"])

SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


class SendOtpRequest(BaseModel):
    """Body of POST /api/v1/user/customer/send-otp-sms/."""

    mobileNumber: Optional[str] = Field(default=None, examples=["9876542168"])
    mobile_number: Optional[str] = None
    countryCode: str = Field(default="+91", examples=["+91"])
    country_code: str = "+91"


class VerifyOtpRequest(BaseModel):
    """Body of POST /api/auth/verify-otp."""

    mobileNumber: Optional[str] = None
    mobile_number: Optional[str] = None
    countryCode: str = "+91"
    country_code: str = "+91"
    otpToken: Optional[str] = None
    otp_token: Optional[str] = None
    challengeId: Optional[str] = None
    challenge_id: Optional[str] = None
    fullName: Optional[str] = None
    display_name: Optional[str] = None


class SwitchAccountRequest(BaseModel):
    accountId: str


@router.get("/api/auth/create-csrf-token")
def create_csrf_token() -> Dict[str, Any]:
    """Issues the CSRF pair the login flow expects to echo back."""
    return AuthenticationService.create_csrf_token()


@router.post("/api/v1/user/customer/send-otp-sms/")
def send_otp_sms(req: SendOtpRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Sends a login OTP to the supplied mobile number."""
    mobile = req.mobileNumber or req.mobile_number or ""
    code = req.countryCode or req.country_code or "+91"
    result = AuthenticationService.send_otp(
        mobile_number=mobile,
        country_code=code,
        db=db,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
            if result.get("retryAfterSeconds")
            else status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Could not send OTP"),
        )
    return result


@router.post("/api/auth/verify-otp")
def verify_otp(
    req: VerifyOtpRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Verifies the OTP, creates/links the shopping account, and starts a session."""
    mobile = req.mobileNumber or req.mobile_number or ""
    otp = req.otpToken or req.otp_token or ""
    name = req.fullName or req.display_name
    code = req.countryCode or req.country_code or "+91"
    challenge = req.challengeId or req.challenge_id
    result = AuthenticationService.verify_otp(
        db=db,
        mobile_number=mobile,
        otp_token=otp,
        display_name=name,
        country_code=code,
        challenge_id=challenge,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Verification failed"),
        )

    token = result["session_token"]
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )

    return {
        "user": result["user"],
        "sessionToken": token,
        "accountId": result["account_id"],
    }


@router.get("/api/auth/session")
def get_session(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the signed-in user together with every linked shopping account."""
    accounts = MultiAccountManager.list_accounts(db, ctx.user.id)
    raw_mobile = decrypt_data(ctx.account.encrypted_mobile) or ""

    return {
        "user": {
            "id": ctx.account.id,
            "userId": ctx.user.id,
            "fullName": ctx.account.display_name,
            "mobileNumber": raw_mobile,
            "countryCode": "+91",
            "isRegistered": True,
            "userType": "CUSTOMER",
        },
        "activeAccountId": ctx.account.id,
        "accounts": accounts,
    }


@router.post("/api/auth/switch-account")
def switch_account(
    req: SwitchAccountRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Repoints the current session at another linked shopping account."""
    switched = AuthenticationService.switch_active_account(db, ctx.session, req.accountId)
    if not switched:
        raise HTTPException(status_code=404, detail="Account not found for this user")

    accounts = MultiAccountManager.list_accounts(db, ctx.user.id)
    return {
        "success": True,
        "activeAccountId": req.accountId,
        "accounts": accounts,
    }


@router.post("/api/auth/logout")
def logout(
    response: Response,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Revokes the session token and clears the session cookie."""
    AuthenticationService.revoke_session(db, ctx.token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"success": True, "message": "Signed out"}
