"""Cart read/write model shared by the cart, checkout, and order routers.

Keeps one authoritative implementation of "what is in this account's cart and
what does it cost", so the cart screen, the checkout preview, and order
placement can never disagree about totals or the applied coupon.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.api.cart import CartService
from backend.api.offers import OfferService
from backend.database.models import Offer, Product, ShoppingCart, ShoppingCartItem
from backend.zepto.cart_state import get_applied_coupon, set_applied_coupon
from backend.zepto.constants import MAX_QUANTITY_PER_ITEM
from backend.zepto.serializers import cart_bill, cart_product, coupon_payload


def find_product(db: Session, store_product_id: str) -> Optional[Product]:
    """Resolves a product by our id or by its external Zepto product id."""
    if not store_product_id:
        return None
    return (
        db.query(Product)
        .filter(
            (Product.id == store_product_id)
            | (Product.external_product_id == store_product_id)
        )
        .first()
    )


def _cart_rows(db: Session, cart_id: str) -> List[ShoppingCartItem]:
    return (
        db.query(ShoppingCartItem)
        .filter(ShoppingCartItem.cart_id == cart_id)
        .order_by(ShoppingCartItem.id.asc())
        .all()
    )


def evaluate_coupon(
    db: Session, code: Optional[str], cart_total: float
) -> Tuple[Optional[Dict[str, Any]], float]:
    """Returns (applied coupon summary, discount in rupees) for a cart total."""
    if not code:
        return None, 0.0
    result = OfferService.validate_and_apply_coupon(db, code, cart_total)
    if not result.get("valid"):
        return None, 0.0

    return (
        {
            "code": result["code"],
            "title": result["title"],
            "offerType": result.get("offerType"),
            "discount": result["discount"],
        },
        float(result["discount"]),
    )


def build_cart_payload(db: Session, account_id: str) -> Dict[str, Any]:
    """Full cart payload: line items, totals, applied coupon, and coupons."""
    cart_details = CartService.get_cart_details(db, account_id)
    cart = db.query(ShoppingCart).filter(ShoppingCart.account_id == account_id).first()
    rows = _cart_rows(db, cart.id) if cart else []

    line_items: List[Dict[str, Any]] = []
    for row in rows:
        product = db.query(Product).filter(Product.id == row.product_id).first()
        if not product:
            continue
        line_items.append(cart_product(product, row.quantity, row.id))

    coupon_code = get_applied_coupon(db, account_id)
    applied_coupon, discount_rupees = evaluate_coupon(
        db, coupon_code, float(cart_details["cartTotal"])
    )
    if coupon_code and not applied_coupon:
        # The cart shrank below the coupon's threshold - drop the stale code.
        set_applied_coupon(db, account_id, None)
        coupon_code = None

    offers = db.query(Offer).filter(Offer.is_active == True).all()  # noqa: E712
    coupons = [
        coupon_payload(offer, float(cart_details["cartTotal"])) for offer in offers
    ]

    payload = cart_bill(
        cart_details,
        line_items,
        coupons=coupons,
        coupon_code=coupon_code if applied_coupon else None,
        coupon_discount_rupees=discount_rupees,
    )
    payload["appliedCoupon"] = applied_coupon
    payload["cartItemCount"] = payload.get("itemsCount", 0)
    payload["grandTotalAmount"] = payload.get("totalPayable", 0)
    payload["bestCoupon"] = max(
        (c for c in coupons if c["isEligible"]),
        key=lambda c: c["potentialDiscount"],
        default=None,
    )
    return payload


def replace_cart(
    db: Session, account_id: str, requested: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Sets the cart to exactly `requested`, returning any rejected entries.

    Each entry needs `storeProductId` and `quantity`. Unknown, unavailable, or
    out-of-stock products are reported back rather than silently dropped.
    """
    cart = CartService.get_or_create_cart(db, account_id)
    db.query(ShoppingCartItem).filter(ShoppingCartItem.cart_id == cart.id).delete()
    db.flush()

    rejected: List[Dict[str, Any]] = []
    merged: Dict[str, int] = {}

    for entry in requested:
        store_product_id = str(entry.get("storeProductId") or entry.get("productId") or "")
        try:
            quantity = int(entry.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0

        product = find_product(db, store_product_id)
        if not product:
            rejected.append({"storeProductId": store_product_id, "reason": "PRODUCT_NOT_FOUND"})
            continue
        if not product.availability or product.stock_quantity <= 0:
            rejected.append({"storeProductId": store_product_id, "reason": "OUT_OF_STOCK"})
            continue
        if quantity <= 0:
            continue

        merged[product.id] = min(
            merged.get(product.id, 0) + quantity, MAX_QUANTITY_PER_ITEM
        )

    for product_id, quantity in merged.items():
        db.add(
            ShoppingCartItem(
                cart_id=cart.id,
                product_id=product_id,
                quantity=quantity,
            )
        )

    db.commit()
    return rejected


def add_product(db: Session, account_id: str, store_product_id: str, quantity: int) -> Dict[str, Any]:
    """Increments a single product, respecting stock and the per-item cap."""
    product = find_product(db, store_product_id)
    if not product:
        return {"success": False, "error": "Product not found"}
    if not product.availability or product.stock_quantity <= 0:
        return {"success": False, "error": f"{product.name} is out of stock"}

    cart = CartService.get_or_create_cart(db, account_id)
    row = (
        db.query(ShoppingCartItem)
        .filter(
            ShoppingCartItem.cart_id == cart.id,
            ShoppingCartItem.product_id == product.id,
        )
        .first()
    )

    current = row.quantity if row else 0
    target = current + max(quantity, 1)
    if target > MAX_QUANTITY_PER_ITEM:
        return {
            "success": False,
            "error": f"You can add at most {MAX_QUANTITY_PER_ITEM} units of this item",
        }
    if target > product.stock_quantity:
        return {
            "success": False,
            "error": f"Only {product.stock_quantity} left in stock",
        }

    if row:
        row.quantity = target
    else:
        db.add(
            ShoppingCartItem(cart_id=cart.id, product_id=product.id, quantity=target)
        )
    db.commit()
    return {"success": True}


def set_quantity(db: Session, account_id: str, store_product_id: str, quantity: int) -> Dict[str, Any]:
    """Sets an exact quantity; 0 removes the line."""
    product = find_product(db, store_product_id)
    if not product:
        return {"success": False, "error": "Product not found"}

    cart = CartService.get_or_create_cart(db, account_id)
    row = (
        db.query(ShoppingCartItem)
        .filter(
            ShoppingCartItem.cart_id == cart.id,
            ShoppingCartItem.product_id == product.id,
        )
        .first()
    )

    if quantity <= 0:
        if row:
            db.delete(row)
            db.commit()
        return {"success": True}

    if quantity > MAX_QUANTITY_PER_ITEM:
        return {
            "success": False,
            "error": f"You can add at most {MAX_QUANTITY_PER_ITEM} units of this item",
        }
    if quantity > product.stock_quantity:
        return {"success": False, "error": f"Only {product.stock_quantity} left in stock"}

    if row:
        row.quantity = quantity
    else:
        db.add(
            ShoppingCartItem(cart_id=cart.id, product_id=product.id, quantity=quantity)
        )
    db.commit()
    return {"success": True}


def clear_cart(db: Session, account_id: str) -> None:
    """Empties the cart and releases any applied coupon."""
    CartService.clear_cart(db, account_id)
    set_applied_coupon(db, account_id, None)
