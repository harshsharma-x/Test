"""Coupons router.

Documented endpoint
    GET /coupon-service/api/v1/coupons/promo_cash

Supporting endpoints
    GET    /coupon-service/api/v1/coupons          - coupons for the cart
    POST   /coupon-service/api/v1/coupons/apply    - apply a code to the cart
    DELETE /coupon-service/api/v1/coupons/apply    - remove the applied code
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.cart import CartService
from backend.api.offers import OfferService
from backend.database.connection import get_db
from backend.database.models import Offer
from backend.zepto.cart_state import set_applied_coupon
from backend.zepto.cart_view import build_cart_payload
from backend.zepto.deps import AuthContext, require_auth
from backend.zepto.money import to_paise
from backend.zepto.serializers import coupon_payload

router = APIRouter(tags=["Coupons"])


class ApplyCouponRequest(BaseModel):
    """Body of the coupon apply endpoint."""

    code: str


@router.get("/coupon-service/api/v1/coupons/promo_cash")
def promo_cash(
    source: str = "PROFILE",
    ctx: AuthContext = Depends(require_auth),
) -> Dict[str, Any]:
    """Promo cash balance; stays empty until a campaign credits the account."""
    return {
        "source": source,
        "totalPromoCash": 0,
        "availablePromoCash": 0,
        "promoCashDetails": [],
    }


@router.get("/coupon-service/api/v1/coupons")
def list_coupons(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Every active coupon annotated with eligibility for this cart."""
    cart = CartService.get_cart_details(db, ctx.account_id)
    cart_total = float(cart["cartTotal"])

    offers = db.query(Offer).filter(Offer.is_active == True).all()  # noqa: E712
    coupons = [coupon_payload(offer, cart_total) for offer in offers]

    return {
        "cartTotal": to_paise(cart_total),
        "coupons": coupons,
        "eligibleCount": sum(1 for c in coupons if c["isEligible"]),
    }


@router.post("/coupon-service/api/v1/coupons/apply")
def apply_coupon(
    req: ApplyCouponRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Validates a coupon against the live cart, then attaches it to the cart."""
    cart = CartService.get_cart_details(db, ctx.account_id)
    cart_total = float(cart["cartTotal"])

    if cart["itemCount"] == 0:
        raise HTTPException(
            status_code=400, detail="Add items to your cart before applying a coupon"
        )

    result = OfferService.validate_and_apply_coupon(db, req.code, cart_total)
    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=result.get("error", "Coupon not applicable"))

    set_applied_coupon(db, ctx.account_id, result["code"])
    payload = build_cart_payload(db, ctx.account_id)
    payload["applied"] = {
        "code": result["code"],
        "title": result["title"],
        "discount": result["discount"],
    }
    return payload


@router.delete("/coupon-service/api/v1/coupons/apply")
def remove_coupon(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Detaches the currently applied coupon from the cart."""
    set_applied_coupon(db, ctx.account_id, None)
    return build_cart_payload(db, ctx.account_id)
