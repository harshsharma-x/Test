"""Offers API: Coupons, promo cash, stacking rules, discount calculations."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.database.models import Offer


class OfferService:
    @staticmethod
    def list_active_offers(db: Session) -> List[Offer]:
        return db.query(Offer).filter(Offer.is_active == True).all()

    @staticmethod
    def get_available_offers_for_cart(db: Session, cart_total: float, account_id: str) -> List[Dict[str, Any]]:
        offers = OfferService.list_active_offers(db)
        results = []
        for off in offers:
            is_eligible = cart_total >= off.min_cart_value
            potential_discount = OfferService.compute_discount(off, cart_total) if is_eligible else 0.0

            results.append(
                {
                    "id": off.id,
                    "code": off.code,
                    "title": off.title,
                    "description": off.description,
                    "offerType": off.offer_type,
                    "discountValue": off.discount_value,
                    "minCartValue": off.min_cart_value,
                    "maxDiscount": off.max_discount,
                    "isEligible": is_eligible,
                    "potentialDiscount": round(potential_discount, 2),
                    "amountNeeded": round(max(0.0, off.min_cart_value - cart_total), 2),
                }
            )
        return results

    @staticmethod
    def compute_discount(offer: Offer, cart_total: float) -> float:
        if cart_total < offer.min_cart_value:
            return 0.0

        if offer.offer_type == "PERCENTAGE":
            raw_discount = (offer.discount_value / 100.0) * cart_total
            if offer.max_discount:
                return min(raw_discount, offer.max_discount)
            return raw_discount
        elif offer.offer_type == "FLAT":
            discount = min(offer.discount_value, cart_total)
            return discount
        elif offer.offer_type == "FREE_DELIVERY":
            return min(offer.discount_value, 25.0)
        return 0.0

    @staticmethod
    def validate_and_apply_coupon(db: Session, code: str, cart_total: float) -> Dict[str, Any]:
        clean_code = code.strip().upper()
        offer = db.query(Offer).filter(Offer.code == clean_code, Offer.is_active == True).first()
        if not offer:
            return {"valid": False, "error": f"Invalid coupon code '{clean_code}'"}

        if cart_total < offer.min_cart_value:
            shortfall = offer.min_cart_value - cart_total
            return {
                "valid": False,
                "error": f"Add ₹{shortfall:.0f} more to apply coupon {clean_code} (Min cart ₹{offer.min_cart_value:.0f})",
            }

        discount = OfferService.compute_discount(offer, cart_total)
        return {
            "valid": True,
            "code": offer.code,
            "title": offer.title,
            "offerType": offer.offer_type,
            "discount": round(discount, 2),
            "newPayable": round(max(0.0, cart_total - discount), 2),
        }
