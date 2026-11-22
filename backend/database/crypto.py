"""Cryptographic utilities for secure token and credential encryption."""
from __future__ import annotations

import base64
import hashlib
import os
from cryptography.fernet import Fernet


def _get_fernet_key() -> bytes:
    secret = os.environ.get("SECRET_KEY", "zepto-platform-default-encryption-key-32bytes!")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_get_fernet_key())


def encrypt_data(plaintext: str | None) -> str | None:
    if not plaintext:
        return None
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_data(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        return _fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def mask_phone_number(phone: str | None) -> str:
    """Format phone as: +91 XXXXX 42168"""
    if not phone:
        return "+91 XXXXX XXXXX"
    cleaned = "".join(c for c in phone if c.isdigit())
    if len(cleaned) == 10:
        return f"+91 XXXXX {cleaned[-5:]}"
    elif len(cleaned) > 10:
        return f"+{cleaned[:-10]} XXXXX {cleaned[-5:]}"
    return f"+91 XXXXX {cleaned}"
