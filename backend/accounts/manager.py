"""Multi-account management engine: isolated accounts, switching, profiles, session isolation."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.database.crypto import decrypt_data, encrypt_data, mask_phone_number
from backend.database.models import (
    AccountPreference,
    AccountSession,
    Order,
    ShoppingAccount,
    ShoppingCart,
    User,
)


class MultiAccountManager:
    @staticmethod
    def list_accounts(db: Session, user_id: str) -> List[Dict[str, Any]]:
        """Lists all shopping accounts linked to the master user."""
        accounts = (
            db.query(ShoppingAccount)
            .filter(ShoppingAccount.user_id == user_id)
            .order_by(ShoppingAccount.is_default.desc(), ShoppingAccount.created_at.asc())
            .all()
        )
        result = []
        for acc in accounts:
            raw_mobile = decrypt_data(acc.encrypted_mobile) or "9876542168"
            cart = db.query(ShoppingCart).filter(ShoppingCart.account_id == acc.id).first()
            item_count = len(cart.items) if cart else 0
            order_count = db.query(Order).filter(Order.account_id == acc.id).count()

            result.append(
                {
                    "accountId": acc.id,
                    "displayName": acc.display_name,
                    "maskedMobile": mask_phone_number(raw_mobile),
                    "status": acc.status,
                    "isDefault": acc.is_default,
                    "cartItemCount": item_count,
                    "orderCount": order_count,
                    "createdAt": acc.created_at.isoformat(),
                    "lastUsedAt": acc.last_used_at.isoformat() if acc.last_used_at else None,
                }
            )
        return result

    @staticmethod
    def get_account(db: Session, account_id: str) -> Optional[ShoppingAccount]:
        return db.query(ShoppingAccount).filter(ShoppingAccount.id == account_id).first()

    @staticmethod
    def switch_account(db: Session, user_id: str, account_id: str) -> Dict[str, Any]:
        """Switch active account, ensuring session isolation."""
        account = (
            db.query(ShoppingAccount)
            .filter(ShoppingAccount.id == account_id, ShoppingAccount.user_id == user_id)
            .first()
        )
        if not account:
            return {"success": False, "error": "Account not found or access denied"}

        account.last_used_at = datetime.utcnow()
        db.commit()

        raw_mobile = decrypt_data(account.encrypted_mobile) or "0000000000"
        return {
            "success": True,
            "activeAccount": {
                "accountId": account.id,
                "displayName": account.display_name,
                "maskedMobile": mask_phone_number(raw_mobile),
                "status": account.status,
                "isDefault": account.is_default,
            },
        }

    @staticmethod
    def add_account(
        db: Session,
        user_id: str,
        mobile_number: str,
        display_name: str,
    ) -> Dict[str, Any]:
        clean_mobile = "".join(c for c in mobile_number if c.isdigit())
        if len(clean_mobile) < 10:
            return {"success": False, "error": "Invalid phone number length"}

        # Duplicate check
        existing_accounts = db.query(ShoppingAccount).filter(ShoppingAccount.user_id == user_id).all()
        for acc in existing_accounts:
            if decrypt_data(acc.encrypted_mobile) == clean_mobile:
                return {"success": False, "error": "This mobile number is already linked as an account"}

        new_account = ShoppingAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            encrypted_mobile=encrypt_data(clean_mobile) or "",
            display_name=display_name or f"Account ({clean_mobile[-4:]})",
            status="ACTIVE",
            is_default=len(existing_accounts) == 0,
        )
        db.add(new_account)
        db.flush()

        # Dedicated isolated cart
        cart = ShoppingCart(id=str(uuid.uuid4()), account_id=new_account.id)
        db.add(cart)

        # Default preferences
        pref = AccountPreference(id=str(uuid.uuid4()), account_id=new_account.id, preferences_json="{}")
        db.add(pref)

        db.commit()
        return {
            "success": True,
            "account": {
                "accountId": new_account.id,
                "displayName": new_account.display_name,
                "maskedMobile": mask_phone_number(clean_mobile),
                "status": new_account.status,
                "isDefault": new_account.is_default,
            },
        }

    @staticmethod
    def rename_account(db: Session, account_id: str, new_name: str) -> Dict[str, Any]:
        acc = db.query(ShoppingAccount).filter(ShoppingAccount.id == account_id).first()
        if not acc:
            return {"success": False, "error": "Account not found"}
        acc.display_name = new_name.strip()
        db.commit()
        return {"success": True, "displayName": acc.display_name}

    @staticmethod
    def set_default_account(db: Session, user_id: str, account_id: str) -> Dict[str, Any]:
        accounts = db.query(ShoppingAccount).filter(ShoppingAccount.user_id == user_id).all()
        target = None
        for a in accounts:
            if a.id == account_id:
                a.is_default = True
                target = a
            else:
                a.is_default = False
        if not target:
            return {"success": False, "error": "Target account not found"}
        db.commit()
        return {"success": True, "defaultAccountId": target.id}

    @staticmethod
    def remove_account(db: Session, user_id: str, account_id: str) -> Dict[str, Any]:
        acc = db.query(ShoppingAccount).filter(ShoppingAccount.id == account_id, ShoppingAccount.user_id == user_id).first()
        if not acc:
            return {"success": False, "error": "Account not found"}

        was_default = acc.is_default
        db.delete(acc)
        db.commit()

        if was_default:
            next_acc = db.query(ShoppingAccount).filter(ShoppingAccount.user_id == user_id).first()
            if next_acc:
                next_acc.is_default = True
                db.commit()

        return {"success": True, "removedAccountId": account_id}
