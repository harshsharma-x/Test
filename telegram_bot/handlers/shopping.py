"""Shopping, catalogue, search, cart, and best-offer handlers for Telegram bot."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from backend.api.cart import CartService
from backend.api.offers import OfferService
from backend.api.products import ProductService
from backend.api.search import SearchService
from backend.database.connection import SessionLocal
from backend.database.models import Product
from backend.offers.engine import BestOfferEngine
from telegram_bot.keyboards.inline import cart_keyboard, category_keyboard, main_menu_keyboard, product_card_keyboard
from telegram_bot.middleware.auth import get_or_create_tg_user

router = Router(name="shopping_router")


@router.message(Command("categories"))
async def cmd_categories(message: Message):
    with SessionLocal() as db:
        res = ProductService.get_page(db)
        categories = []
        for w in res.get("pageLayout", {}).get("widgets", []):
            if w.get("widgetType") == "CATEGORY_GRID":
                categories = w.get("categories", [])
                break

    await message.answer(
        "🛍️ <b>Select a Category to Browse:</b>",
        parse_mode="HTML",
        reply_markup=category_keyboard(categories),
    )


@router.callback_query(lambda c: c.data == "nav_categories")
async def cb_nav_categories(callback: CallbackQuery):
    with SessionLocal() as db:
        res = ProductService.get_page(db)
        categories = []
        for w in res.get("pageLayout", {}).get("widgets", []):
            if w.get("widgetType") == "CATEGORY_GRID":
                categories = w.get("categories", [])
                break

    await callback.message.edit_text(
        "🛍️ <b>Select a Category to Browse:</b>",
        parse_mode="HTML",
        reply_markup=category_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("cat_"))
async def cb_select_category(callback: CallbackQuery):
    cat_prefix = callback.data.replace("cat_", "")
    with SessionLocal() as db:
        products = db.query(Product).filter(Product.category.ilike(f"%{cat_prefix}%")).limit(6).all()

    if not products:
        await callback.answer("No products found in category", show_alert=True)
        return

    await callback.message.answer(f"📦 <b>Products in {cat_prefix}:</b>", parse_mode="HTML")
    for p in products:
        savings = p.original_price - p.price
        disc_text = f" ({p.discount_percent}% off)" if p.discount_percent > 0 else ""
        text = (
            f"🛒 <b>{p.name}</b>\n"
            f"🏷️ Brand: {p.brand} | Unit: {p.unit}\n"
            f"💰 <b>₹{p.price:.0f}</b> <strike>₹{p.original_price:.0f}</strike>{disc_text}\n"
            f"⭐ Rating: {p.rating} / 5.0"
        )
        await callback.message.answer(text, parse_mode="HTML", reply_markup=product_card_keyboard(p.id))

    await callback.answer()


@router.message(Command("search"))
async def cmd_search(message: Message):
    query = message.text.replace("/search", "").strip()
    if not query:
        await message.answer("Please specify a search term. Example: <code>/search milk</code>", parse_mode="HTML")
        return

    with SessionLocal() as db:
        res = SearchService.search_products(db, query)
        items = res.get("items", [])

    if not items:
        await message.answer(f"🔍 No products found for '<b>{query}</b>'. Try 'milk', 'mango', or 'chips'.", parse_mode="HTML")
        return

    await message.answer(f"🔍 Found {len(items)} items for '<b>{query}</b>':", parse_mode="HTML")
    for it in items[:5]:
        disc_text = f" ({it['discountPercent']}% off)" if it['discountPercent'] > 0 else ""
        text = (
            f"🛒 <b>{it['name']}</b>\n"
            f"🏷️ Brand: {it['brand']} | Unit: {it['unit']}\n"
            f"💰 <b>₹{it['price']:.0f}</b> <strike>₹{it['originalPrice']:.0f}</strike>{disc_text}"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=product_card_keyboard(it['id']))


@router.callback_query(lambda c: c.data.startswith("add_"))
async def cb_add_to_cart(callback: CallbackQuery):
    prod_id = callback.data.replace("add_", "")
    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, callback.from_user.id, callback.from_user.full_name)
        cart = CartService.add_to_cart(db, account.id, prod_id, quantity=1)

    await callback.answer("Added to cart! 🛒")
    await callback.message.edit_reply_markup(reply_markup=product_card_keyboard(prod_id, in_cart=1))


@router.message(Command("cart"))
@router.callback_query(lambda c: c.data in ["nav_cart", "view_cart"])
async def show_cart(event: Message | CallbackQuery):
    user_id = event.from_user.id
    full_name = event.from_user.full_name

    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, user_id, full_name)
        cart = CartService.get_cart_details(db, account.id)

    if cart["itemCount"] == 0:
        empty_text = (
            f"🛒 <b>Your Cart is Empty!</b>\n\n"
            f"Account: <b>{account.display_name}</b>\n"
            f"Browse categories or search to start shopping with 10-minute delivery."
        )
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(empty_text, parse_mode="HTML", reply_markup=cart_keyboard(has_items=False))
            await event.answer()
        else:
            await event.answer(empty_text, parse_mode="HTML", reply_markup=cart_keyboard(has_items=False))
        return

    lines = [f"🛒 <b>Shopping Cart ({account.display_name}):</b>\n"]
    for it in cart["items"]:
        lines.append(f"• <b>{it['name']}</b> x {it['quantity']} = ₹{it['total']:.0f}")

    lines.append(f"\n💵 <b>Item Total:</b> ₹{cart['cartTotal']:.0f}")
    if cart["itemDiscount"] > 0:
        lines.append(f"🎉 <b>MRP Savings:</b> ₹{cart['itemDiscount']:.0f}")

    if cart["deliveryFee"] == 0:
        lines.append(f"🚚 <b>Delivery Fee:</b> FREE (10-Min Express)")
    else:
        lines.append(f"🚚 <b>Delivery Fee:</b> ₹{cart['deliveryFee']:.0f} (Add ₹{cart['amountNeededForFreeDelivery']:.0f} for free delivery)")

    lines.append(f"💳 <b>Total Payable:</b> <b>₹{cart['finalPayable']:.0f}</b>")

    cart_text = "\n".join(lines)
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(cart_text, parse_mode="HTML", reply_markup=cart_keyboard(has_items=True))
        await event.answer()
    else:
        await event.answer(cart_text, parse_mode="HTML", reply_markup=cart_keyboard(has_items=True))


@router.callback_query(lambda c: c.data == "apply_best_offer")
async def cb_apply_best_offer(callback: CallbackQuery):
    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, callback.from_user.id, callback.from_user.full_name)
        res = BestOfferEngine.auto_apply_best_offer(db, account.id)

    if res.get("success"):
        off = res["appliedOffer"]
        text = (
            f"⚡ <b>BEST OFFER APPLIED!</b>\n\n"
            f"🏷️ <b>Coupon:</b> <code>{off['code']}</code>\n"
            f"🎉 <b>Discount Saved:</b> ₹{off['discountAmount']:.0f}\n"
            f"💵 <b>New Cart Total:</b> ₹{off['finalPayable']:.0f}\n\n"
            f"<i>{off['savingsMessage']}</i>"
        )
        await callback.message.answer(text, parse_mode="HTML", reply_markup=cart_keyboard(has_items=True))
        await callback.answer("Best offer applied!")
    else:
        await callback.answer(res.get("message", "No eligible offer found"), show_alert=True)


@router.callback_query(lambda c: c.data == "cart_clear")
async def cb_cart_clear(callback: CallbackQuery):
    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, callback.from_user.id, callback.from_user.full_name)
        CartService.clear_cart(db, account.id)

    await callback.message.edit_text("🛒 Your cart has been cleared.", reply_markup=cart_keyboard(has_items=False))
    await callback.answer("Cart cleared")


@router.message(Command("offers"))
@router.callback_query(lambda c: c.data == "nav_best_offer")
async def show_offers(event: Message | CallbackQuery):
    with SessionLocal() as db:
        user, account = get_or_create_tg_user(db, event.from_user.id, event.from_user.full_name)
        eval_data = BestOfferEngine.evaluate_best_offer(db, account.id)

    lines = ["⚡ <b>Available Promotional Offers & Coupons:</b>\n"]
    if eval_data.get("hasEligibleOffer"):
        rec = eval_data["recommendedOffer"]
        lines.append(f"🌟 <b>Recommended:</b> <code>{rec['code']}</code> (Saves ₹{rec['discountAmount']:.0f})\n")

    for off in eval_data["evaluatedOffers"]:
        elig_badge = "✅ Eligible" if off["isEligible"] else f"⚪ Min cart ₹{off['minCartValue']:.0f}"
        lines.append(f"• <b>{off['code']}</b> - {off['title']} [{elig_badge}]")

    lines.append("\nTap 'AUTO APPLY BEST OFFER' in your cart to maximize savings!")
    text = "\n".join(lines)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
