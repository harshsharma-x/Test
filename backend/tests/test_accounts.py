"""Test Suite for Authentication and Multi-Account Management."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.accounts.manager import MultiAccountManager
from backend.api.authentication import AuthenticationService
from backend.database.models import Base, User


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        user = User(id="user_test_master", telegram_id="tg_12345")
        db.add(user)
        db.commit()
        yield db
    finally:
        db.close()


def test_csrf_token_generation():
    csrf = AuthenticationService.create_csrf_token()
    assert csrf["ok"] is True
    assert "csrfToken" in csrf
    assert "csrfSecret" in csrf


def test_otp_flow(test_db):
    # Send OTP
    send_res = AuthenticationService.send_otp("9876543210")
    assert send_res["success"] is True

    # Verify invalid OTP
    bad_verify = AuthenticationService.verify_otp(
        test_db, "9876543210", "000000", user_id="user_test_master"
    )
    assert bad_verify["success"] is False

    # Verify valid OTP (123456)
    good_verify = AuthenticationService.verify_otp(
        test_db, "9876543210", "123456", display_name="Primary", user_id="user_test_master"
    )
    assert good_verify["success"] is True
    assert "session_token" in good_verify
    assert good_verify["user"]["fullName"] == "Primary"


def test_multi_account_isolation(test_db):
    # Add Account 1
    acc1_res = MultiAccountManager.add_account(test_db, "user_test_master", "9876543210", "Personal")
    assert acc1_res["success"] is True
    acc1_id = acc1_res["account"]["accountId"]

    # Add Account 2
    acc2_res = MultiAccountManager.add_account(test_db, "user_test_master", "9123456789", "Work")
    assert acc2_res["success"] is True
    acc2_id = acc2_res["account"]["accountId"]

    # Prevent duplicate
    dup_res = MultiAccountManager.add_account(test_db, "user_test_master", "9876543210", "Personal Copy")
    assert dup_res["success"] is False

    # List accounts
    accounts = MultiAccountManager.list_accounts(test_db, "user_test_master")
    assert len(accounts) == 2

    # Switch account
    switch_res = MultiAccountManager.switch_account(test_db, "user_test_master", acc2_id)
    assert switch_res["success"] is True
    assert switch_res["activeAccount"]["accountId"] == acc2_id

    # Rename account
    rename_res = MultiAccountManager.rename_account(test_db, acc2_id, "Work Pro")
    assert rename_res["success"] is True
    assert rename_res["displayName"] == "Work Pro"

    # Remove account
    del_res = MultiAccountManager.remove_account(test_db, "user_test_master", acc1_id)
    assert del_res["success"] is True
    assert len(MultiAccountManager.list_accounts(test_db, "user_test_master")) == 1
