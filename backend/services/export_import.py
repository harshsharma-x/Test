"""Account Import and Export Engine."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from backend.database.crypto import decrypt_data, encrypt_data, mask_phone_number
from backend.database.models import AccountPreference, ShoppingAccount, ShoppingCart


class AccountBackupService:
    VERSION = 1

    @staticmethod
    def export_accounts(db: Session, user_id: str) -> Dict[str, Any]:
        """Generates a secure JSON backup of accounts. Plaintext tokens are NEVER exported."""
        accounts = db.query(ShoppingAccount).filter(ShoppingAccount.user_id == user_id).all()
        exported_accounts = []

        for acc in accounts:
            raw_phone = decrypt_data(acc.encrypted_mobile) or "9876542168"
            pref = db.query(AccountPreference).filter(AccountPreference.account_id == acc.id).first()
            prefs_data = json.loads(pref.preferences_json) if pref and pref.preferences_json else {}

            exported_accounts.append(
                {
                    "account_id": acc.id,
                    "display_name": acc.display_name,
                    "mobile": mask_phone_number(raw_phone),
                    "is_default": acc.is_default,
                    "session_status": "reauthentication_required",
                    "preferences": prefs_data,
                    "metadata": {
                        "created_at": acc.created_at.isoformat(),
                        "last_used_at": acc.last_used_at.isoformat() if acc.last_used_at else None,
                    },
                }
            )

        return {
            "version": AccountBackupService.VERSION,
            "export_date": datetime.utcnow().isoformat() + "Z",
            "accounts_count": len(exported_accounts),
            "accounts": exported_accounts,
        }

    @staticmethod
    def preview_import(db: Session, user_id: str, import_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validates payload schema and previews accounts before importing."""
        if not isinstance(import_payload, dict):
            return {"valid": False, "error": "Invalid JSON root object"}

        version = import_payload.get("version")
        if version != AccountBackupService.VERSION:
            return {"valid": False, "error": f"Unsupported backup version {version}"}

        accounts_to_import = import_payload.get("accounts", [])
        if not isinstance(accounts_to_import, list):
            return {"valid": False, "error": "'accounts' must be a valid array"}

        existing_accounts = db.query(ShoppingAccount).filter(ShoppingAccount.user_id == user_id).all()
        existing_ids = {a.id for a in existing_accounts}

        preview_items = []
        for acc_data in accounts_to_import:
            acc_id = acc_data.get("account_id")
            display_name = acc_data.get("display_name", "Imported Account")
            masked_mobile = acc_data.get("mobile", "+91 XXXXX XXXXX")
            is_dup = acc_id in existing_ids

            preview_items.append(
                {
                    "accountId": acc_id,
                    "displayName": display_name,
                    "maskedMobile": masked_mobile,
                    "isDuplicate": is_dup,
                    "action": "SKIP (Already Present)" if is_dup else "IMPORT_NEW",
                }
            )

        return {
            "valid": True,
            "totalCount": len(accounts_to_import),
            "newCount": sum(1 for p in preview_items if not p["isDuplicate"]),
            "duplicateCount": sum(1 for p in preview_items if p["isDuplicate"]),
            "preview": preview_items,
        }

    @staticmethod
    def confirm_import(
        db: Session,
        user_id: str,
        import_payload: Dict[str, Any],
        overwrite_duplicates: bool = False,
    ) -> Dict[str, Any]:
        """Imports and restores accounts into database with isolated carts and preferences."""
        validation = AccountBackupService.preview_import(db, user_id, import_payload)
        if not validation.get("valid"):
            return {"success": False, "error": validation.get("error")}

        imported_count = 0
        existing_accounts = {a.id: a for a in db.query(ShoppingAccount).filter(ShoppingAccount.user_id == user_id).all()}

        for acc_data in import_payload.get("accounts", []):
            acc_id = acc_data.get("account_id") or str(uuid.uuid4())
            display_name = acc_data.get("display_name", "Restored Account")
            # Note: For security, mobile is restored masked until re-authenticated with OTP
            masked_mobile = acc_data.get("mobile", "+91 XXXXX 00000")
            is_default = acc_data.get("is_default", False)
            preferences = acc_data.get("preferences", {})

            if acc_id in existing_accounts:
                if overwrite_duplicates:
                    existing = existing_accounts[acc_id]
                    existing.display_name = display_name
                    imported_count += 1
                continue

            new_acc = ShoppingAccount(
                id=acc_id,
                user_id=user_id,
                encrypted_mobile=encrypt_data(masked_mobile) or "",
                display_name=display_name,
                status="REAUTHENTICATION_REQUIRED",
                is_default=is_default,
            )
            db.add(new_acc)
            db.flush()

            # Create isolated cart
            cart = ShoppingCart(id=str(uuid.uuid4()), account_id=new_acc.id)
            db.add(cart)

            # Restore preferences
            pref = AccountPreference(
                id=str(uuid.uuid4()),
                account_id=new_acc.id,
                preferences_json=json.dumps(preferences),
            )
            db.add(pref)
            imported_count += 1

        db.commit()
        return {
            "success": True,
            "importedCount": imported_count,
            "message": f"Successfully imported {imported_count} account(s). Please verify mobile via OTP to activate sessions.",
        }
