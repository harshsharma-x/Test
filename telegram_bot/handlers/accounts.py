"""Multi-account management and Backup command handlers for Telegram bot."""
from __future__ import annotations

import json
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from backend.accounts.manager import MultiAccountManager
from backend.api.users import UserService
from backend.database.connection import SessionLocal
from backend.database.crypto import decrypt_data, mask_phone_number
from backend.services.export_import import AccountBackupService
from telegram_bot.keyboards.inline import account_switcher_keyboard, main_menu_keyboard
from telegram_bot.middleware.auth import get_or_create_tg_user

router = Router(name="accounts_router")


@router.message(Command("accounts"))
@router.message(Command("switch"))
async def cmd_accounts(message: Message):
    with SessionLocal() as db:
        user, active_account = get_or_create_tg_user(db, message.from_user.id, message.from_user.full_name)
        accounts = MultiAccountManager.list_accounts(db, user.id)

    text = (
        "👥 <b>Multi-Account Switcher</b>\n\n"
        "Switch between your shopping accounts instantly. Each account has isolated carts, addresses, and order histories:\n\n"
        f"<b>Currently Active:</b> {active_account.display_name}\n\n"
        "Tap an account below to switch:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=account_switcher_keyboard(accounts, active_account.id))


@router.callback_query(lambda c: c.data == "nav_accounts")
async def cb_nav_accounts(callback: CallbackQuery):
    with SessionLocal() as db:
        user, active_account = get_or_create_tg_user(db, callback.from_user.id, callback.from_user.full_name)
        accounts = MultiAccountManager.list_accounts(db, user.id)

    text = (
        "👥 <b>Multi-Account Switcher</b>\n\n"
        f"<b>Currently Active:</b> {active_account.display_name}\n"
        "Tap an account below to switch:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=account_switcher_keyboard(accounts, active_account.id))
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("switch_to_"))
async def cb_switch_account(callback: CallbackQuery):
    target_id = callback.data.replace("switch_to_", "")
    with SessionLocal() as db:
        user, _ = get_or_create_tg_user(db, callback.from_user.id, callback.from_user.full_name)
        res = MultiAccountManager.switch_account(db, user.id, target_id)
        accounts = MultiAccountManager.list_accounts(db, user.id)

    if res.get("success"):
        acc = res["activeAccount"]
        await callback.message.edit_text(
            f"✅ <b>Switched to {acc['displayName']}!</b>\n\n"
            f"📱 Mobile: <code>{acc['maskedMobile']}</code>\n"
            f"🛒 Cart and order history are now isolated for this profile.",
            parse_mode="HTML",
            reply_markup=account_switcher_keyboard(accounts, target_id),
        )
        await callback.answer(f"Active account: {acc['displayName']}")
    else:
        await callback.answer("Failed to switch account", show_alert=True)


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    with SessionLocal() as db:
        user, active_account = get_or_create_tg_user(db, message.from_user.id, message.from_user.full_name)
        info = UserService.get_customer_info(db, active_account.id)
        pass_info = UserService.get_pass_overview(db, active_account.id)
        wallet = UserService.get_wallet_balances(db, active_account.id)

    u = info["user"]
    prof_text = (
        f"👤 <b>Customer Profile</b>\n\n"
        f"<b>Name:</b> {u['fullName']}\n"
        f"<b>Mobile:</b> <code>{u['mobileNumber']}</code>\n"
        f"<b>Status:</b> Active Customer\n"
        f"<b>Referral Code:</b> <code>{u['referralCode']}</code>\n\n"
        f"💳 <b>Zepto Wallet:</b> {wallet['totalBalanceNumericalAbbreviation']}\n"
        f"⭐ <b>Zepto Pass:</b> {pass_info['variantName']} ({pass_info['passLockedStateText']})\n"
        f"💰 <b>Lifetime Savings:</b> ₹{pass_info['lifetimeSavings']['totalSavingsAmount']:.0f}"
    )
    await message.answer(prof_text, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.message(Command("export"))
async def cmd_export(message: Message):
    with SessionLocal() as db:
        user, _ = get_or_create_tg_user(db, message.from_user.id, message.from_user.full_name)
        backup_data = AccountBackupService.export_accounts(db, user.id)

    json_str = json.dumps(backup_data, indent=2)
    file_bytes = json_str.encode("utf-8")
    doc = BufferedInputFile(file_bytes, filename=f"zepto_accounts_backup_{user.id[:8]}.json")

    await message.answer_document(
        document=doc,
        caption=(
            f"💾 <b>Account Export Successful!</b>\n\n"
            f"Exported <b>{backup_data['accounts_count']} account(s)</b>.\n"
            f"🔒 <i>Note: Tokens and passwords are never exported in plaintext for your security.</i>"
        ),
        parse_mode="HTML",
    )


@router.message(Command("import"))
async def cmd_import(message: Message):
    await message.answer(
        "📥 <b>Account Import</b>\n\n"
        "To import accounts, send a valid JSON backup file here, or use the web application at <code>/account/import</code>.",
        parse_mode="HTML",
    )
