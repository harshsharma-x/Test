"""Authentication command handlers for Telegram bot."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove

from backend.api.authentication import AuthenticationService
from backend.database.connection import SessionLocal
from telegram_bot.keyboards.inline import main_menu_keyboard, phone_request_keyboard
from telegram_bot.middleware.auth import get_or_create_tg_user

router = Router(name="auth_router")


class LoginStates(StatesGroup):
    waiting_for_mobile = State()
    waiting_for_otp = State()


@router.message(Command("login"))
async def cmd_login(message: Message, state: FSMContext):
    await state.set_state(LoginStates.waiting_for_mobile)
    await message.answer(
        "📱 <b>Zepto Mobile Login</b>\n\n"
        "Please enter your 10-digit mobile number, or tap the button below to share your contact:",
        parse_mode="HTML",
        reply_markup=phone_request_keyboard(),
    )


@router.message(LoginStates.waiting_for_mobile, F.contact)
async def process_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await _send_otp_for_phone(message, state, phone)


@router.message(LoginStates.waiting_for_mobile)
async def process_mobile_text(message: Message, state: FSMContext):
    phone = message.text.strip()
    await _send_otp_for_phone(message, state, phone)


async def _send_otp_for_phone(message: Message, state: FSMContext, phone: str):
    clean = "".join(c for c in phone if c.isdigit())
    if len(clean) < 10:
        await message.answer("❌ Invalid mobile number. Please enter a valid 10-digit number:")
        return

    res = await AuthenticationService.send_otp(clean)
    await state.update_data(mobile=clean)
    await state.set_state(LoginStates.waiting_for_otp)

    msg = res.get("data", {}).get("msg", "OTP sent via SMS.")
    await message.answer(
        f"📩 <b>Verification Code Sent!</b>\n\n"
        f"{msg}\n\n"
        f"Enter the 6-digit OTP (use <code>123456</code> in test mode):",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(LoginStates.waiting_for_otp)
async def process_otp(message: Message, state: FSMContext):
    otp = message.text.strip()
    data = await state.get_data()
    mobile = data.get("mobile", "")

    with SessionLocal() as db:
        user, _ = get_or_create_tg_user(db, message.from_user.id, message.from_user.full_name)
        res = await AuthenticationService.verify_otp(
            db=db,
            mobile_number=mobile,
            otp_token=otp,
            display_name=f"{message.from_user.first_name}'s Account",
            user_id=user.id,
        )

    if res.get("success"):
        await state.clear()
        u = res["user"]
        await message.answer(
            f"✅ <b>Successfully Logged In!</b>\n\n"
            f"👤 <b>Account:</b> {u['fullName']}\n"
            f"📱 <b>Mobile:</b> {u['mobileNumber']}\n"
            f"🎁 <b>Referral Code:</b> <code>{u['referralCode']}</code>\n\n"
            f"You can now switch between this and your other accounts anytime via /switch.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await message.answer(
            f"❌ <b>Verification Failed:</b> {res.get('error', 'Invalid OTP')}\n\n"
            f"Please enter the correct 6-digit OTP (or <code>123456</code>):",
            parse_mode="HTML",
        )
