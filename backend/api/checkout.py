"""Checkout API: Order summary, fee calculations, delivery slots, validation."""
from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from backend.api.addresses import AddressService
from backend.api.cart import CartService
from backend.api.offers import OfferService


class CheckoutService:
    @staticmethod
    def get_checkout_summary(
        db: Session,
        account_id: str,
        coupon_code: Optional[str] = None,
        address_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculates bill details, delivery fee, discounts, and payable amount."""
        cart_info = CartService.get_cart_details(db, account_id)
        cart_total = cart_info["cartTotal"]

        if cart_info["itemCount"] == 0:
            return {
                "valid": False,
                "error": "Shopping cart is empty. Add items to checkout.",
                "cart": cart_info,
            }

        # Apply coupon if provided
        discount_amount = 0.0
        applied_coupon = None
        delivery_discount = 0.0

        if coupon_code:
            coupon_res = OfferService.validate_and_apply_coupon(db, coupon_code, cart_total)
            if coupon_res.get("valid"):
                applied_coupon = {
                    "code": coupon_res["code"],
                    "title": coupon_res["title"],
                    "discount": coupon_res["discount"],
                }
                if coupon_res.get("offerType") == "FREE_DELIVERY":
                    delivery_discount = cart_info["deliveryFee"]
                else:
                    discount_amount = coupon_res["discount"]

        effective_delivery_fee = max(0.0, cart_info["deliveryFee"] - delivery_discount)
        handling_fee = 4.0  # Small standard platform fee
        final_payable = max(0.0, (cart_total - discount_amount) + effective_delivery_fee + handling_fee)

        # Addresses
        addresses = AddressService.get_addresses(db, account_id)
        selected_address = next((a for a in addresses if a.get("id") == address_id), addresses[0] if addresses else None)

        return {
            "valid": True,
            "cart": cart_info,
            "selectedAddress": selected_address,
            "billBreakdown": {
                "mrpTotal": cart_info["mrpTotal"],
                "itemDiscount": cart_info["itemDiscount"],
                "cartTotal": cart_total,
                "couponDiscount": round(discount_amount, 2),
                "appliedCoupon": applied_coupon,
                "deliveryFee": cart_info["deliveryFee"],
                "deliveryDiscount": delivery_discount,
                "effectiveDeliveryFee": effective_delivery_fee,
                "handlingFee": handling_fee,
                "totalSavings": round(cart_info["itemDiscount"] + discount_amount + delivery_discount, 2),
                "finalPayable": round(final_payable, 2),
            },
            "etaMinutes": 10,
        }
