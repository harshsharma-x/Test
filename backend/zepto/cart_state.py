"""Per-account cart state that outlives a single request.

The applied coupon and the selected delivery address are attached to the
account's `AccountPreference` row. Every write merges into the existing JSON
blob so the saved-address list and cart state never clobber each other.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.database.models import AccountPreference

KEY_APPLIED_COUPON = "appliedCouponCode"
KEY_SELECTED_ADDRESS = "selectedAddressId"


def read_prefs(db: Session, account_id: str) -> Dict[str, Any]:
    """Returns the account's preference blob, or an empty dict."""
    pref = (
        db.query(AccountPreference)
        .filter(AccountPreference.account_id == account_id)
        .first()
    )
    if not pref or not pref.preferences_json:
        return {}
    try:
        data = json.loads(pref.preferences_json)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_prefs(db: Session, account_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merges `updates` into the preference blob and returns the merged result."""
    merged = read_prefs(db, account_id)
    merged.update(updates)

    pref = (
        db.query(AccountPreference)
        .filter(AccountPreference.account_id == account_id)
        .first()
    )
    if not pref:
        pref = AccountPreference(id=str(uuid.uuid4()), account_id=account_id)
        db.add(pref)

    pref.preferences_json = json.dumps(merged)
    db.commit()
    return merged


def get_applied_coupon(db: Session, account_id: str) -> Optional[str]:
    """The coupon the account currently has applied to its cart, if any."""
    return read_prefs(db, account_id).get(KEY_APPLIED_COUPON)


def set_applied_coupon(db: Session, account_id: str, code: Optional[str]) -> None:
    write_prefs(db, account_id, {KEY_APPLIED_COUPON: code})


def get_selected_address(db: Session, account_id: str) -> Optional[str]:
    """The address id the account chose for its next delivery."""
    return read_prefs(db, account_id).get(KEY_SELECTED_ADDRESS)


def set_selected_address(db: Session, account_id: str, address_id: Optional[str]) -> None:
    write_prefs(db, account_id, {KEY_SELECTED_ADDRESS: address_id})
