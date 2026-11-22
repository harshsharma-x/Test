"""Telegram authentication and session middleware."""
from __future__ import annotations

import uuid
from typing import Tuple
from sqlalchemy.orm import Session

from backend.database.crypto import encrypt_data
from backend.database.models import ShoppingAccount, ShoppingCart, User


def get_or_create_tg_user(db: Session, telegram_id: int | str, full_name: str = "Telegram Shopper") -> Tuple[User, ShoppingAccount]:
    """Resolves or provisions master User and active ShoppingAccount for a Telegram user."""
    tg_str = str(telegram_id)
    user = db.query(User).filter(User.telegram_id == tg_str).first()

    if not user:
        user = User(id=str(uuid.uuid4()), telegram_id=tg_str)
        db.add(user)
        db.flush()

        # Create primary default shopping account for this telegram user
        default_account = ShoppingAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            encrypted_mobile=encrypt_data("9876542168") or "",
            display_name=f"{full_name} (Personal)",
            status="ACTIVE",
            is_default=True,
        )
        db.add(default_account)
        db.flush()

        cart = ShoppingCart(id=str(uuid.uuid4()), account_id=default_account.id)
        db.add(cart)
        db.commit()
        return user, default_account

    # User exists: find default or most recently used account
    active_account = (
        db.query(ShoppingAccount)
        .filter(ShoppingAccount.user_id == user.id)
        .order_by(ShoppingAccount.last_used_at.desc(), ShoppingAccount.is_default.desc())
        .first()
    )

    if not active_account:
        active_account = ShoppingAccount(
            id=str(uuid.uuid4()),
            user_id=user.id,
            encrypted_mobile=encrypt_data("9876542168") or "",
            display_name=f"{full_name} (Personal)",
            status="ACTIVE",
            is_default=True,
        )
        db.add(active_account)
        db.flush()
        cart = ShoppingCart(id=str(uuid.uuid4()), account_id=active_account.id)
        db.add(cart)
        db.commit()

    return user, active_account
