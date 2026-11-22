"""Test Suite for Backup Portability and Services."""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.accounts.manager import MultiAccountManager
from backend.database.models import Base, User
from backend.services.export_import import AccountBackupService


@pytest.fixture
def backup_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSession()
    try:
        user = User(id="user_backup_test")
        db.add(user)
        db.commit()

        # Add accounts
        MultiAccountManager.add_account(db, user.id, "9876543210", "Personal Acc")
        MultiAccountManager.add_account(db, user.id, "9123456789", "Work Acc")

        yield db
    finally:
        db.close()


def test_export_accounts_security_and_structure(backup_db):
    exported = AccountBackupService.export_accounts(backup_db, "user_backup_test")
    assert exported["version"] == 1
    assert exported["accounts_count"] == 2
    assert len(exported["accounts"]) == 2

    acc1 = exported["accounts"][0]
    assert acc1["display_name"] == "Personal Acc"
    assert "XXXXX" in acc1["mobile"]
    assert acc1["session_status"] == "reauthentication_required"

    # Security check: Plaintext tokens or passwords must never exist
    dumped = json.dumps(exported)
    assert "encrypted_access_token" not in dumped
    assert "password" not in dumped
    assert "session_id" not in dumped


def test_import_validation_and_preview(backup_db):
    exported = AccountBackupService.export_accounts(backup_db, "user_backup_test")

    # Preview with same accounts (should detect duplicates)
    preview = AccountBackupService.preview_import(backup_db, "user_backup_test", exported)
    assert preview["valid"] is True
    assert preview["totalCount"] == 2
    assert preview["duplicateCount"] == 2
    assert preview["newCount"] == 0

    # Modify export with a brand new account
    new_account_payload = {
        "version": 1,
        "accounts": [
            {
                "account_id": "new-uuid-001",
                "display_name": "Vacation Home",
                "mobile": "+91 XXXXX 99999",
                "is_default": False,
                "preferences": {"favoriteCategory": "Fruits"},
            }
        ],
    }

    preview_new = AccountBackupService.preview_import(backup_db, "user_backup_test", new_account_payload)
    assert preview_new["valid"] is True
    assert preview_new["newCount"] == 1
    assert preview_new["duplicateCount"] == 0

    # Confirm Import
    confirm_res = AccountBackupService.confirm_import(backup_db, "user_backup_test", new_account_payload)
    assert confirm_res["success"] is True
    assert confirm_res["importedCount"] == 1

    # Verify restored account exists in DB
    all_accounts = MultiAccountManager.list_accounts(backup_db, "user_backup_test")
    assert len(all_accounts) == 3
    assert any(a["displayName"] == "Vacation Home" for a in all_accounts)
