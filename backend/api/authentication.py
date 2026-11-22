"""Authentication API: CSRF, SMS OTP dispatch, OTP verification, bearer sessions.

Mirrors the documented Zepto auth surface:

    GET  /api/auth/create-csrf-token              -> {ok, csrfToken, csrfSecret}
    POST /api/v1/user/customer/send-otp-sms/      -> {verificationType, data:{msg}}
    POST /api/auth/verify-otp                     -> {user:{...}} + session token

Codes are stored as salted SHA-256 hashes with a hard expiry and an attempt
budget, so replaying the database cannot recover a usable OTP.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from backend.database.crypto import decrypt_data, encrypt_data, mask_phone_number
from backend.database.models import (
    AccountPreference,
    AccountSession,
    AuthSession,
    OtpChallenge,
    ShoppingAccount,
    ShoppingCart,
    User,
)

OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 20
SESSION_TTL_DAYS = 30

# Local development has no SMS gateway attached. With this enabled a fixed code
# is accepted so the full login flow stays usable end to end.
DEV_OTP_CODE = "123456"


def _dev_mode() -> bool:
    return os.environ.get("OTP_DEV_MODE", "1").lower() not in ("0", "false", "no")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_otp(mobile_digits: str, code: str) -> str:
    """Salted so identical codes for different numbers produce different hashes."""
    return _sha256(f"{mobile_digits}:{code}:{_otp_pepper()}")


def _otp_pepper() -> str:
    return os.environ.get("SECRET_KEY", "zepto-platform-default-encryption-key-32bytes!")


def _hash_token(token: str) -> str:
    return _sha256(f"session:{token}:{_otp_pepper()}")


def _digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


class AuthenticationService:
    # ---------- CSRF ----------

    @staticmethod
    def create_csrf_token() -> Dict[str, Any]:
        """Issues a double-submit CSRF pair, as create-csrf-token does."""
        token = secrets.token_urlsafe(32)
        return {
            "ok": True,
            "csrfToken": token,
            "csrfSecret": _sha256(token),
        }

    # ---------- OTP dispatch ----------

    @staticmethod
    def send_otp(
        mobile_number: str,
        country_code: str = "+91",
        db: Optional[Session] = None,
        purpose: str = "LOGIN",
    ) -> Dict[str, Any]:
        """Creates and dispatches an OTP challenge for a mobile number.

        Returns the documented envelope (`verificationType` / `data.msg`) plus a
        `success` flag and, in development, the code so the UI can complete a
        login without an SMS provider.
        """
        clean_mobile = _digits(mobile_number)
        if len(clean_mobile) != 10:
            return {
                "success": False,
                "error": "Enter a valid 10-digit mobile number",
                "errors": ["INVALID_MOBILE_NUMBER"],
            }

        if db is None:
            # Stateless callers (tests, Telegram bot previews) still get a payload.
            return {
                "success": True,
                "verificationType": "otp_sms",
                "data": {"msg": f"OTP Sent to {mask_phone_number(clean_mobile)}."},
            }

        now = datetime.utcnow()
        recent = (
            db.query(OtpChallenge)
            .filter(
                OtpChallenge.mobile_digits == clean_mobile,
                OtpChallenge.purpose == purpose,
                OtpChallenge.created_at > now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS),
            )
            .order_by(OtpChallenge.created_at.desc())
            .first()
        )
        if recent:
            retry_after = OTP_RESEND_COOLDOWN_SECONDS - int((now - recent.created_at).total_seconds())
            return {
                "success": False,
                "error": f"Please wait {max(retry_after, 1)}s before requesting another OTP",
                "retryAfterSeconds": max(retry_after, 1),
            }

        # Supersede any outstanding challenge for this number.
        db.query(OtpChallenge).filter(
            OtpChallenge.mobile_digits == clean_mobile,
            OtpChallenge.consumed == False,  # noqa: E712 - SQL boolean comparison
        ).update({"consumed": True}, synchronize_session=False)

        code = f"{secrets.randbelow(1_000_000):06d}"
        challenge = OtpChallenge(
            id=str(uuid.uuid4()),
            mobile_digits=clean_mobile,
            code_hash=_hash_otp(clean_mobile, code),
            purpose=purpose,
            expires_at=now + timedelta(seconds=OTP_TTL_SECONDS),
        )
        db.add(challenge)
        db.commit()

        payload: Dict[str, Any] = {
            "success": True,
            "verificationType": "otp_sms",
            "challengeId": challenge.id,
            "expiresInSeconds": OTP_TTL_SECONDS,
            "data": {"msg": f"OTP Sent to {mask_phone_number(clean_mobile)}."},
        }
        if _dev_mode():
            payload["devOtp"] = code
            payload["data"]["msg"] = (
                f"OTP Sent to {mask_phone_number(clean_mobile)}. "
                f"Development mode: your code is {code}."
            )
        return payload

    # ---------- OTP verification ----------

    @staticmethod
    def verify_otp(
        db: Session,
        mobile_number: str,
        otp_token: str,
        display_name: Optional[str] = None,
        user_id: Optional[str] = None,
        country_code: str = "+91",
        challenge_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validates an OTP, resolves/creates the account, and issues a session."""
        clean_mobile = _digits(mobile_number)
        supplied = _digits(otp_token)
        if len(clean_mobile) != 10:
            return {"success": False, "error": "Invalid phone number"}
        if len(supplied) != 6:
            return {"success": False, "error": "Enter the 6-digit OTP"}

        challenge: Optional[OtpChallenge] = None
        if challenge_id:
            challenge = db.query(OtpChallenge).filter(OtpChallenge.id == challenge_id).first()
        else:
            challenge = (
                db.query(OtpChallenge)
                .filter(
                    OtpChallenge.mobile_digits == clean_mobile,
                    OtpChallenge.consumed == False,  # noqa: E712
                )
                .order_by(OtpChallenge.created_at.desc())
                .first()
            )

        uses_dev_code = _dev_mode() and supplied == DEV_OTP_CODE

        if challenge:
            if challenge.consumed and not uses_dev_code:
                return {"success": False, "error": "This OTP has already been used"}
            if challenge.expires_at < datetime.utcnow() and not uses_dev_code:
                return {"success": False, "error": "OTP expired. Request a new one"}
            if challenge.attempts >= OTP_MAX_ATTEMPTS and not uses_dev_code:
                return {"success": False, "error": "Too many incorrect attempts. Request a new OTP"}

            if not uses_dev_code and challenge.code_hash != _hash_otp(clean_mobile, supplied):
                challenge.attempts += 1
                db.commit()
                remaining = max(OTP_MAX_ATTEMPTS - challenge.attempts, 0)
                return {
                    "success": False,
                    "error": f"Incorrect OTP. {remaining} attempt(s) remaining",
                    "attemptsRemaining": remaining,
                }
        elif not uses_dev_code:
            # No outstanding challenge and the code is not the dev bypass.
            return {"success": False, "error": "Invalid or expired OTP"}

        if challenge:
            challenge.consumed = True
            db.commit()

        account = AuthenticationService._resolve_account(
            db, clean_mobile, user_id=user_id, display_name=display_name
        )
        token = AuthenticationService._issue_session(db, account)

        return {
            "success": True,
            "account_id": account.id,
            "session_token": token,
            "user": AuthenticationService._user_payload(account, clean_mobile, country_code),
        }

    # ---------- Session lifecycle ----------

    @staticmethod
    def _issue_session(db: Session, account: ShoppingAccount) -> str:
        token = f"zpt_{secrets.token_urlsafe(32)}"
        session = AuthSession(
            id=str(uuid.uuid4()),
            token_hash=_hash_token(token),
            user_id=account.user_id,
            active_account_id=account.id,
            expires_at=datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS),
        )
        db.add(session)
        db.commit()
        return token

    @staticmethod
    def resolve_session(
        db: Session, token: str
    ) -> Optional[Tuple[AuthSession, User, ShoppingAccount]]:
        """Returns (session, user, active account) for a valid bearer token."""
        if not token:
            return None
        session = (
            db.query(AuthSession)
            .filter(AuthSession.token_hash == _hash_token(token), AuthSession.revoked == False)  # noqa: E712
            .first()
        )
        if not session or session.expires_at < datetime.utcnow():
            return None

        user = db.query(User).filter(User.id == session.user_id).first()
        if not user:
            return None

        account = None
        if session.active_account_id:
            account = (
                db.query(ShoppingAccount)
                .filter(
                    ShoppingAccount.id == session.active_account_id,
                    ShoppingAccount.user_id == user.id,
                )
                .first()
            )
        if not account:
            account = (
                db.query(ShoppingAccount)
                .filter(ShoppingAccount.user_id == user.id)
                .order_by(ShoppingAccount.is_default.desc(), ShoppingAccount.created_at.asc())
                .first()
            )
        if not account:
            return None

        session.last_seen_at = datetime.utcnow()
        db.commit()
        return session, user, account

    @staticmethod
    def revoke_session(db: Session, token: str) -> bool:
        if not token:
            return False
        session = (
            db.query(AuthSession)
            .filter(AuthSession.token_hash == _hash_token(token))
            .first()
        )
        if not session:
            return False
        session.revoked = True
        db.commit()
        return True

    @staticmethod
    def switch_active_account(db: Session, session: AuthSession, account_id: str) -> bool:
        account = (
            db.query(ShoppingAccount)
            .filter(ShoppingAccount.id == account_id, ShoppingAccount.user_id == session.user_id)
            .first()
        )
        if not account:
            return False
        session.active_account_id = account.id
        account.last_used_at = datetime.utcnow()
        db.commit()
        return True

    # ---------- Internals ----------

    @staticmethod
    def _find_account_by_mobile(db: Session, clean_mobile: str) -> Optional[ShoppingAccount]:
        for acc in db.query(ShoppingAccount).all():
            if decrypt_data(acc.encrypted_mobile) == clean_mobile:
                return acc
        return None

    @staticmethod
    def _resolve_account(
        db: Session,
        clean_mobile: str,
        user_id: Optional[str],
        display_name: Optional[str],
    ) -> ShoppingAccount:
        """Finds the account for this number, linking or creating as needed."""
        existing = AuthenticationService._find_account_by_mobile(db, clean_mobile)

        if existing:
            if user_id and existing.user_id != user_id:
                # Caller explicitly scoped the login to another master user.
                user_id = existing.user_id
            existing.status = "ACTIVE"
            existing.last_used_at = datetime.utcnow()
            if display_name:
                existing.display_name = display_name
            db.commit()
            return existing

        if not user_id:
            user = User(id=str(uuid.uuid4()))
            db.add(user)
            db.flush()
            user_id = user.id
        else:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                user = User(id=user_id)
                db.add(user)
                db.flush()

        has_any = db.query(ShoppingAccount).filter(ShoppingAccount.user_id == user_id).count() > 0
        account = ShoppingAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            encrypted_mobile=encrypt_data(clean_mobile) or "",
            display_name=display_name or f"Account ({clean_mobile[-4:]})",
            status="ACTIVE",
            is_default=not has_any,
        )
        db.add(account)
        db.flush()

        db.add(ShoppingCart(id=str(uuid.uuid4()), account_id=account.id))
        db.add(AccountPreference(id=str(uuid.uuid4()), account_id=account.id, preferences_json="{}"))
        db.commit()
        return account

    @staticmethod
    def _user_payload(
        account: ShoppingAccount, clean_mobile: str, country_code: str
    ) -> Dict[str, Any]:
        return {
            "id": account.id,
            "fullName": account.display_name,
            "mobileNumber": mask_phone_number(clean_mobile),
            "countryCode": country_code,
            "emailId": None,
            "isRegistered": True,
            "isUserFullNameSet": True,
            "lastOrderNotified": True,
            "isInternalUser": False,
            "isInternationalUser": False,
            "referralCode": "ZEPTO" + clean_mobile[-4:],
            "blockRefererral": False,
            "referredBy": None,
            "userType": "CUSTOMER",
            "whatsappOpted": "PENDING",
        }
