"""Start and Help command handlers for Telegram bot."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from backend.database.connection import SessionLocal
from backend.database.crypto import decrypt_data, mask_phone_number
from telegram_bot.keyboards.inline import main_menu_keyboard
from telegram_bot.middleware.auth import get_or_create_tg_user

router = Router(name="start_router")


@router.message(Command("start"))
async def cmd_start(message: Message):
    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, message.from_user.id, message.from_user.full_name)
        phone = decrypt_data(account.encrypted_mobile) or "9876542168"
        masked = mask_phone_number(phone)

    welcome_text = (
        f"⚡ <b>Welcome to Zepto Shopping Ecosystem!</b>\n\n"
        f"🚀 <i>Groceries & essentials delivered in 10 minutes.</i>\n\n"
        f"👤 <b>Active Account:</b> {account.display_name}\n"
        f"📱 <b>Mobile:</b> <code>{masked}</code>\n"
        f"🟢 <b>Status:</b> Active\n\n"
        f"Choose an option below to begin:"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 <b>Zepto Telegram Bot Commands:</b>\n\n"
        "🛍️ <b>Shopping:</b>\n"
        "/categories - Browse all grocery categories\n"
        "/search &lt;query&gt; - Search for items (e.g. <code>/search milk</code>)\n"
        "/cart - View and manage your current shopping cart\n"
        "/offers - View discount coupons and best offers\n\n"
        "👥 <b>Multi-Account Management:</b>\n"
        "/accounts - View all linked shopping accounts\n"
        "/switch - Switch between your personal and secondary accounts\n"
        "/login - Log into a new phone number via OTP\n"
        "/profile - View active customer profile & Zepto Pass\n\n"
        "📦 <b>Checkout & Orders:</b>\n"
        "/checkout - Review bill and place 10-minute order\n"
        "/orders - View order history and reorder items\n"
        "/track - Real-time rider tracking and live ETA\n"
        "/address - View or update delivery address\n\n"
        "💾 <b>Data Portability:</b>\n"
        "/export - Download secure JSON backup of your accounts\n"
        "/import - Restore account profiles from JSON backup\n"
        "/support - Customer support and FAQs"
    )
    await message.answer(help_text, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.callback_query(lambda c: c.data == "nav_main")
async def cb_nav_main(callback: CallbackQuery):
    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, callback.from_user.id, callback.from_user.full_name)
        phone = decrypt_data(account.encrypted_mobile) or "9876542168"
        masked = mask_phone_number(phone)

    text = (
        f"⚡ <b>Zepto Shopping Dashboard</b>\n\n"
        f"👤 <b>Active:</b> {account.display_name} ({masked})\n"
        f"Select an action below:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
    await callback.answer()
