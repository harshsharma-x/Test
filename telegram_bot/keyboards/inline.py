"""Inline keyboards for Telegram shopping bot."""
from __future__ import annotations

from typing import Any, Dict, List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🛍️ Browse Categories", callback_data="nav_categories"),
                InlineKeyboardButton(text="🔍 Search Items", callback_data="nav_search"),
            ],
            [
                InlineKeyboardButton(text="🛒 View Cart", callback_data="nav_cart"),
                InlineKeyboardButton(text="⚡ Best Offers", callback_data="nav_best_offer"),
            ],
            [
                InlineKeyboardButton(text="👥 Switch Account", callback_data="nav_accounts"),
                InlineKeyboardButton(text="📦 My Orders", callback_data="nav_orders"),
            ],
            [
                InlineKeyboardButton(text="📥 Import / Export", callback_data="nav_backup"),
                InlineKeyboardButton(text="💬 Support & FAQs", callback_data="nav_support"),
            ],
        ]
    )


def category_keyboard(categories: List[str]) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(text=cat, callback_data=f"cat_{cat[:20]}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Back to Menu", callback_data="nav_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_card_keyboard(product_id: str, in_cart: int = 0) -> InlineKeyboardMarkup:
    if in_cart > 0:
        row = [
            InlineKeyboardButton(text="➖", callback_data=f"dec_{product_id}"),
            InlineKeyboardButton(text=f"🛒 {in_cart} in cart", callback_data=f"view_cart"),
            InlineKeyboardButton(text="➕", callback_data=f"inc_{product_id}"),
        ]
    else:
        row = [InlineKeyboardButton(text="🛒 Add to Cart", callback_data=f"add_{product_id}")]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            row,
            [InlineKeyboardButton(text="🔙 Back", callback_data="nav_categories")],
        ]
    )


def cart_keyboard(has_items: bool = True) -> InlineKeyboardMarkup:
    if not has_items:
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🛍️ Start Shopping", callback_data="nav_categories")]]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ AUTO APPLY BEST OFFER", callback_data="apply_best_offer")],
            [InlineKeyboardButton(text="💳 Proceed to Checkout", callback_data="nav_checkout")],
            [
                InlineKeyboardButton(text="➕ Add More Items", callback_data="nav_categories"),
                InlineKeyboardButton(text="🗑️ Clear Cart", callback_data="cart_clear"),
            ],
            [InlineKeyboardButton(text="🔙 Main Menu", callback_data="nav_main")],
        ]
    )


def account_switcher_keyboard(accounts: List[Dict[str, Any]], active_id: str) -> InlineKeyboardMarkup:
    buttons = []
    for acc in accounts:
        is_active = acc["accountId"] == active_id
        mark = "✅ " if is_active else "⚪ "
        label = f"{mark}{acc['displayName']} ({acc['maskedMobile']})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"switch_to_{acc['accountId']}")])

    buttons.append([InlineKeyboardButton(text="➕ Add New Shopping Account", callback_data="acc_add")])
    buttons.append([InlineKeyboardButton(text="🔙 Main Menu", callback_data="nav_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def phone_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Share Phone Number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
