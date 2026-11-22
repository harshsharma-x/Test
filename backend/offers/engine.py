"""Intelligent Automatic Best-Offer Engine."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.api.cart import CartService
from backend.api.offers import OfferService
from backend.database.models import Offer


class BestOfferEngine:
    @staticmethod
    def evaluate_best_offer(db: Session, account_id: str) -> Dict[str, Any]:
        """Evaluates all legitimate offers against the account's active cart and identifies the optimal choice."""
        cart_info = CartService.get_cart_details(db, account_id)
        cart_total = cart_info["cartTotal"]
        delivery_fee = cart_info["deliveryFee"]

        if cart_total <= 0:
            return {
                "hasEligibleOffer": False,
                "recommendedOffer": None,
                "evaluatedOffers": [],
                "cartTotal": 0.0,
                "savingsAmount": 0.0,
                "finalPayable": 0.0,
                "message": "Cart is empty. Add items to discover eligible offers.",
            }

        active_offers: List[Offer] = OfferService.list_active_offers(db)
        evaluated = []
        best_offer: Optional[Offer] = None
        max_discount: float = 0.0

        for off in active_offers:
            is_eligible = cart_total >= off.min_cart_value
            discount = 0.0
            if is_eligible:
                discount = OfferService.compute_discount(off, cart_total)

            evaluated.append(
                {
                    "id": off.id,
                    "code": off.code,
                    "title": off.title,
                    "description": off.description,
                    "offerType": off.offer_type,
                    "minCartValue": off.min_cart_value,
                    "maxDiscount": off.max_discount,
                    "isEligible": is_eligible,
                    "calculatedDiscount": round(discount, 2),
                    "amountNeeded": round(max(0.0, off.min_cart_value - cart_total), 2),
                }
            )

            if is_eligible and discount > max_discount:
                max_discount = discount
                best_offer = off

        recommended_data = None
        if best_offer and max_discount > 0:
            effective_del_fee = 0.0 if best_offer.offer_type == "FREE_DELIVERY" else delivery_fee
            final_payable = max(0.0, (cart_total - max_discount) + effective_del_fee)

            recommended_data = {
                "id": best_offer.id,
                "code": best_offer.code,
                "title": best_offer.title,
                "offerType": best_offer.offer_type,
                "discountAmount": round(max_discount, 2),
                "originalCartTotal": cart_total,
                "finalPayable": round(final_payable, 2),
                "deliveryFee": round(effective_del_fee, 2),
                "savingsMessage": f"You save ₹{max_discount:.0f} with coupon {best_offer.code}!",
            }

        return {
            "hasEligibleOffer": recommended_data is not None,
            "recommendedOffer": recommended_data,
            "evaluatedOffers": evaluated,
            "cartTotal": cart_total,
            "deliveryFee": delivery_fee,
            "savingsAmount": round(max_discount, 2),
            "finalPayable": round(recommended_data["finalPayable"] if recommended_data else (cart_total + delivery_fee), 2),
        }

    @staticmethod
    def auto_apply_best_offer(db: Session, account_id: str) -> Dict[str, Any]:
        """Automatically confirms and applies the best eligible offer to the cart checkout."""
        evaluation = BestOfferEngine.evaluate_best_offer(db, account_id)
        if not evaluation.get("hasEligibleOffer"):
            return {
                "success": False,
                "message": "No eligible offers found for the current cart value.",
                "evaluation": evaluation,
            }

        rec = evaluation["recommendedOffer"]
        return {
            "success": True,
            "appliedOffer": rec,
            "message": f"Successfully auto-applied {rec['code']}! You saved ₹{rec['discountAmount']:.0f}.",
            "finalPayable": rec["finalPayable"],
        }
