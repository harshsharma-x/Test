"""Test Suite for Telegram Bot Handlers and Keyboards."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.models import Base
from telegram_bot.keyboards.inline import (
    account_switcher_keyboard,
    cart_keyboard,
    category_keyboard,
    main_menu_keyboard,
    phone_request_keyboard,
    product_card_keyboard,
)
from telegram_bot.middleware.auth import get_or_create_tg_user


@pytest.fixture
def tg_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def test_telegram_keyboards():
    # 1. Main menu
    kb_main = main_menu_keyboard()
    assert len(kb_main.inline_keyboard) == 4

    # 2. Categories
    kb_cat = category_keyboard(["Dairy", "Fruits", "Snacks", "Beverages"])
    assert len(kb_cat.inline_keyboard) >= 2

    # 3. Product card keyboard
    kb_prod_empty = product_card_keyboard("p123", in_cart=0)
    assert kb_prod_empty.inline_keyboard[0][0].callback_data == "add_p123"

    kb_prod_active = product_card_keyboard("p123", in_cart=3)
    assert kb_prod_active.inline_keyboard[0][0].text == "➖"
    assert "3 in cart" in kb_prod_active.inline_keyboard[0][1].text
    assert kb_prod_active.inline_keyboard[0][2].text == "➕"

    # 4. Cart keyboard
    kb_cart_full = cart_keyboard(has_items=True)
    assert any("AUTO APPLY BEST OFFER" in b.text for row in kb_cart_full.inline_keyboard for b in row)

    # 5. Account switcher
    accounts_mock = [
        {"accountId": "a1", "displayName": "Personal", "maskedMobile": "+91 XXXXX 11111"},
        {"accountId": "a2", "displayName": "Work", "maskedMobile": "+91 XXXXX 22222"},
    ]
    kb_acc = account_switcher_keyboard(accounts_mock, active_id="a1")
    assert "✅ Personal" in kb_acc.inline_keyboard[0][0].text
    assert "⚪ Work" in kb_acc.inline_keyboard[1][0].text

    # 6. Phone request keyboard
    kb_phone = phone_request_keyboard()
    assert kb_phone.keyboard[0][0].request_contact is True


def test_telegram_user_provisioning(tg_db):
    user, account = get_or_create_tg_user(tg_db, telegram_id=987654321, full_name="John Doe")
    assert user.telegram_id == "987654321"
    assert account.display_name == "John Doe (Personal)"
    assert account.is_default is True

    # Same user returning
    user2, account2 = get_or_create_tg_user(tg_db, telegram_id=987654321, full_name="John Doe")
    assert user2.id == user.id
    assert account2.id == account.id
