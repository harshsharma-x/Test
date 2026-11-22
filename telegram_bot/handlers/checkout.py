"""Checkout, Orders, Tracking, and Support handlers for Telegram bot."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from backend.api.addresses import AddressService
from backend.api.checkout import CheckoutService
from backend.api.delivery import DeliveryService
from backend.api.orders import OrderService
from backend.api.support import SupportService
from backend.database.connection import SessionLocal
from telegram_bot.keyboards.inline import main_menu_keyboard
from telegram_bot.middleware.auth import get_or_create_tg_user

router = Router(name="checkout_router")


@router.message(Command("checkout"))
@router.callback_query(lambda c: c.data == "nav_checkout")
async def process_checkout(event: Message | CallbackQuery):
    user_id = event.from_user.id
    full_name = event.from_user.full_name

    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, user_id, full_name)
        summary = CheckoutService.get_checkout_summary(db, account.id)

    if not summary.get("valid"):
        err = summary.get("error", "Your cart is empty.")
        if isinstance(event, CallbackQuery):
            await event.answer(err, show_alert=True)
        else:
            await event.answer(f"❌ {err}")
        return

    b = summary["billBreakdown"]
    addr = summary.get("selectedAddress", {})
    addr_text = f"{addr.get('flatDetails', '402')}, {addr.get('buildingName', 'Emerald Heights')}, {addr.get('city', 'Mumbai')}"

    text = (
        f"💳 <b>Zepto 10-Minute Express Checkout</b>\n\n"
        f"👤 Account: <b>{account.display_name}</b>\n"
        f"📍 Delivering To: <i>{addr_text}</i>\n"
        f"⚡ Estimated Delivery: <b>10 mins</b>\n\n"
        f"🧾 <b>Bill Breakdown:</b>\n"
        f"• Items Total: ₹{b['cartTotal']:.0f}\n"
        f"• Delivery Fee: ₹{b['effectiveDeliveryFee']:.0f}\n"
        f"• Handling Fee: ₹{b['handlingFee']:.0f}\n"
    )

    if b.get("appliedCoupon"):
        text += f"• Coupon Discount ({b['appliedCoupon']['code']}): -₹{b['couponDiscount']:.0f}\n"

    text += (
        f"\n🎉 <b>Total Savings: ₹{b['totalSavings']:.0f}</b>\n"
        f"💰 <b>Final Amount to Pay: ₹{b['finalPayable']:.0f}</b>\n\n"
        f"Choose payment method to place order:"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Pay via UPI (Instant)", callback_data="pay_upi")],
            [InlineKeyboardButton(text="💵 Cash on Delivery", callback_data="pay_cod")],
            [InlineKeyboardButton(text="🔙 Back to Cart", callback_data="nav_cart")],
        ]
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(lambda c: c.data in ["pay_upi", "pay_cod"])
async def confirm_order(callback: CallbackQuery):
    method = "UPI" if callback.data == "pay_upi" else "COD"
    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, callback.from_user.id, callback.from_user.full_name)
        res = OrderService.create_order(db, account.id, payment_method=method)

    if res.get("success"):
        o = res["order"]
        text = (
            f"🎉 <b>ORDER PLACED SUCCESSFULLY!</b> ⚡\n\n"
            f"🆔 <b>Order Code:</b> <code>{o['orderCode']}</code>\n"
            f"👤 <b>Account:</b> {account.display_name}\n"
            f"💰 <b>Amount:</b> ₹{o['totalAmount']:.0f} ({method})\n"
            f"⏱️ <b>ETA:</b> Arriving in ~{o['etaMinutes']} minutes!\n\n"
            f"📍 <i>Rider assigned and packing at nearest Dark Store.</i>\n"
            f"Use /track to follow your delivery partner in real-time."
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🚴 Track Live Order", callback_data=f"track_{o['id']}")],
                [InlineKeyboardButton(text="🛍️ Continue Shopping", callback_data="nav_categories")],
            ]
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await callback.answer("Order confirmed!")
    else:
        await callback.answer(f"Failed to place order: {res.get('error')}", show_alert=True)


@router.message(Command("orders"))
@router.callback_query(lambda c: c.data == "nav_orders")
async def show_orders(event: Message | CallbackQuery):
    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, event.from_user.id, event.from_user.full_name)
        orders = OrderService.list_orders(db, account.id)

    if not orders:
        text = f"📦 <b>No Previous Orders</b>\n\nAccount: <b>{account.display_name}</b> has not placed any orders yet."
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
            await event.answer()
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
        return

    lines = [f"📦 <b>Order History ({account.display_name}):</b>\n"]
    for o in orders[:5]:
        lines.append(f"• <b>{o['orderCode']}</b> | ₹{o['totalAmount']:.0f} | <b>{o['status']}</b>")

    lines.append("\nUse /track to view live ETA for your latest order.")
    text = "\n".join(lines)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.message(Command("track"))
@router.callback_query(lambda c: c.data.startswith("track_"))
async def show_tracking(event: Message | CallbackQuery):
    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, event.from_user.id, event.from_user.full_name)
        orders = OrderService.list_orders(db, account.id)

    if not orders:
        msg = "You have no active orders to track."
        if isinstance(event, CallbackQuery):
            await event.answer(msg, show_alert=True)
        else:
            await event.answer(msg)
        return

    latest = orders[0]
    live = DeliveryService.get_live_tracking(latest["id"])

    text = (
        f"🚴 <b>Live Order Tracking</b>\n\n"
        f"📦 <b>Order:</b> <code>{latest['orderCode']}</code>\n"
        f"🟢 <b>Status:</b> {latest['status']}\n"
        f"⏱️ <b>ETA:</b> {live['currentEtaMinutes']} minutes\n\n"
        f"👤 <b>Rider:</b> {live['rider']['name']} (⭐ {live['rider']['rating']})\n"
        f"🛵 <b>Vehicle:</b> {live['rider']['vehicle']}\n"
        f"📱 <b>Contact:</b> {live['rider']['phone']}\n\n"
        f"📍 Delivering to your saved address."
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.message(Command("address"))
async def cmd_address(message: Message):
    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, message.from_user.id, message.from_user.full_name)
        addrs = AddressService.get_addresses(db, account.id)

    lines = [f"📍 <b>Saved Delivery Addresses ({account.display_name}):</b>\n"]
    for a in addrs:
        def_tag = " (Default)" if a.get("isDefault") else ""
        lines.append(f"• <b>{a.get('name')}</b>{def_tag}: {a.get('flatDetails')}, {a.get('buildingName')}, {a.get('city')}")

    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=main_menu_keyboard())


@router.message(Command("support"))
@router.callback_query(lambda c: c.data == "nav_support")
async def show_support(event: Message | CallbackQuery):
    faqs = SupportService.get_faq_topics()
    lines = ["💬 <b>Zepto Customer Support & FAQs</b>\n"]
    for f in faqs:
        lines.append(f"❓ <b>{f['topic']}</b>\n👉 {f['answer']}\n")

    lines.append("Need immediate assistance? Contact support@zepto.com or use web chat.")
    text = "\n".join(lines)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
