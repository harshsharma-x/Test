"""Orders router.

Documented endpoints
    GET  /api/v2/order/
    POST /pfs-postorder/api/v1/get-page/ORDER_DETAILS
    GET  /post-order-service/api/v2/order/last-ongoing-order
    POST /samiksha-service/api/v1/order-rating

Supporting endpoints
    GET  /post-order-service/api/v2/order/{order_id}
    POST /post-order-service/api/v1/order/{order_id}/cancel

Order placement is not present in the captured traffic, so it is exposed on the
same `order-service` path style the other order services use.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.addresses import AddressService
from backend.api.orders import OrderService
from backend.api.support import SupportService
from backend.database.connection import get_db
from backend.database.models import Order
from backend.zepto import payment_gateway
from backend.zepto.cart_state import get_selected_address, set_applied_coupon, set_selected_address
from backend.zepto.cart_view import build_cart_payload
from backend.zepto.constants import DEFAULT_STORE_ID
from backend.zepto.deps import AuthContext, require_auth
from backend.zepto.money import to_paise, to_rupees
from backend.zepto.serializers import order_detail, order_summary

router = APIRouter(tags=["Orders"])

ACTIVE_STATUSES = ("PLACED", "PACKING", "OUT_FOR_DELIVERY")


class PlaceOrderRequest(BaseModel):
    """Body for placing an order. `paymentReference` comes from the gateway."""

    paymentMethod: str = Field(default="UPI", examples=["UPI", "CARD", "WALLET", "COD"])
    paymentReference: Optional[str] = Field(
        default=None, description="Reference returned by the payment confirm call."
    )
    addressId: Optional[str] = None
    deliveryInstructions: Optional[str] = None


class OrderDetailsRequest(BaseModel):
    """Body of POST /pfs-postorder/api/v1/get-page/ORDER_DETAILS."""

    orderId: str
    page_size: int = 8
    isArchived: bool = False
    enforce_platform_type: str = "DESKTOP"


class OrderRatingRequest(BaseModel):
    """Body of POST /samiksha-service/api/v1/order-rating."""

    order_id: str
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    feedback: str = ""


def _order_for_account(db: Session, account_id: str, order_id: str) -> Optional[Order]:
    """Fetches an order, scoped to the caller's account."""
    return (
        db.query(Order)
        .filter(Order.id == order_id, Order.account_id == account_id)
        .first()
    )


def _resolve_address(db: Session, account_id: str, requested_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Picks the requested address, else the saved selection, else the default."""
    addresses = AddressService.get_addresses(db, account_id)
    if not addresses:
        return None

    wanted = requested_id or get_selected_address(db, account_id)
    for address in addresses:
        if address.get("id") == wanted:
            return address

    for address in addresses:
        if address.get("isDefault"):
            return address

    return addresses[0]


@router.post("/order-service/api/v1/orders/create")
def place_order(
    req: PlaceOrderRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Places a paid order, then empties the cart."""
    cart = build_cart_payload(db, ctx.account_id)
    if cart["itemsCount"] == 0:
        raise HTTPException(status_code=400, detail="Your cart is empty")

    payable_paise = int(cart["totalPayable"])
    method = req.paymentMethod.strip().upper()
    address = _resolve_address(db, ctx.account_id, req.addressId)
    if not address:
        raise HTTPException(
            status_code=400, detail="Add a delivery address before placing an order"
        )

    transaction = None
    if method == "COD":
        payment_status = "COD_DUE"
    elif req.paymentReference:
        verification = payment_gateway.verify_paid(
            db, req.paymentReference, ctx.account_id, to_rupees(payable_paise)
        )
        if not verification.get("ok"):
            raise HTTPException(status_code=400, detail=verification.get("error"))
        transaction = verification["transaction"]
        payment_status = "PAID"
    else:
        payment_status = "PAID"

    result = OrderService.create_order(
        db,
        account_id=ctx.account_id,
        payment_method=method,
        address_id=address.get("id"),
        coupon_code=cart.get("appliedCouponCode"),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Could not place order"))

    order = db.query(Order).filter(Order.id == result["order"]["id"]).first()
    order.payment_method = method
    order.payment_status = payment_status
    order.transaction_reference = req.paymentReference if method != "COD" else None
    if req.deliveryInstructions:
        order.delivery_address = f"{order.delivery_address} | Note: {req.deliveryInstructions}"

    if transaction:
        transaction.order_id = order.id

    set_selected_address(db, ctx.account_id, address.get("id"))
    set_applied_coupon(db, ctx.account_id, None)
    db.commit()

    return {
        "success": True,
        "order": order_summary(order),
        "payment": {
            "method": method,
            "status": payment_status,
            "reference": order.transaction_reference,
            "formattedAmount": cart["totalPayable"],
        },
        "deliveryAddress": {
            "id": address.get("id"),
            "label": address.get("label") or address.get("name"),
            "formattedAddress": " ".join(
                part
                for part in (
                    address.get("flatDetails"),
                    address.get("buildingName"),
                    address.get("city"),
                    address.get("pincode"),
                )
                if part
            ),
        },
    }


@router.get("/api/v2/order/")
def list_orders(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Paginated order history for the active account."""
    orders = (
        db.query(Order)
        .filter(Order.account_id == ctx.account_id)
        .order_by(Order.created_at.desc())
        .limit(50)
        .all()
    )
    return {
        "orders": [order_summary(order) for order in orders],
        "endOfList": True,
        "totalOrders": len(orders),
        "recommendedProducts": [],
        "minimumProductsRequired": 0,
        "carouselPosition": 0,
        "nextPageParams": None,
    }


@router.get("/post-order-service/api/v2/order/last-ongoing-order")
def last_ongoing_order(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """The order currently on its way, if there is one."""
    order = (
        db.query(Order)
        .filter(Order.account_id == ctx.account_id, Order.status.in_(ACTIVE_STATUSES))
        .order_by(Order.created_at.desc())
        .first()
    )

    if not order:
        return {
            "backgroundColor": "",
            "bannerType": None,
            "carouselBackgroundColor": "",
            "carouselItemColor": "",
            "carouselTextColor": "",
            "img": "",
            "ongoingOrders": [],
            "orderId": None,
            "orderPlacedAt": None,
            "orderStatus": "DELIVERED",
            "subtitle": "",
            "textColor": "",
            "title": "",
        }

    return {
        "backgroundColor": "#E5FAEC",
        "bannerType": "ONGOING",
        "carouselBackgroundColor": "#FFFFFF",
        "carouselItemColor": "#FFFFFF",
        "carouselTextColor": "#262A33",
        "img": "",
        "ongoingOrders": [order_summary(order)],
        "orderId": order.id,
        "orderPlacedAt": order.created_at.isoformat() + "Z",
        "orderStatus": order.status,
        "subtitle": f"Arriving in about {order.eta_minutes} minutes",
        "textColor": "#262A33",
        "title": "On the way",
    }


@router.post("/pfs-postorder/api/v1/get-page/ORDER_DETAILS")
def order_details_page(
    req: OrderDetailsRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Full detail page for one order: items, address, payment, timeline."""
    order = _order_for_account(db, ctx.account_id, req.orderId)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_detail(order)


@router.get("/post-order-service/api/v2/order/{order_id}")
def get_order(
    order_id: str,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Convenience GET for the same order detail payload."""
    order = _order_for_account(db, ctx.account_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_detail(order)


@router.post("/post-order-service/api/v1/order/{order_id}/cancel")
def cancel_order(
    order_id: str,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Cancels an order that has not been delivered yet."""
    order = _order_for_account(db, ctx.account_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status in ("DELIVERED", "CANCELLED"):
        raise HTTPException(
            status_code=400, detail=f"Order is already {order.status.lower()}"
        )

    was_paid = order.payment_status == "PAID"
    result = OrderService.cancel_order(db, order_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    if was_paid:
        order.payment_status = "REFUNDED"
        if order.transaction_reference:
            transaction = payment_gateway.get(db, order.transaction_reference)
            if transaction:
                transaction.status = "REFUNDED"
                transaction.order_id = None
                db.commit()

    return {
        "success": True,
        "orderId": order.id,
        "status": order.status,
        "paymentStatus": order.payment_status,
        "refundInitiated": was_paid,
    }


@router.post("/samiksha-service/api/v1/order-rating")
def rate_order(
    req: OrderRatingRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the rating layout for an order, or records the submitted rating."""
    order = _order_for_account(db, ctx.account_id, req.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if req.rating is None:
        return {
            "isUserInExperiment": True,
            "isRatingSkipped": False,
            "orderId": order.id,
            "orderCode": order.external_order_id,
            "productRatingLayoutConfig": {
                "isImageEnabled": True,
                "isPillEnabled": True,
                "uiConfig": {
                    "isProfileReviewAndEarn": "true",
                    "isReviewAndEarn": "true",
                    "orderRatingDesign": "v2",
                    "stripPosition": "floating",
                },
            },
            "ratingOptions": [
                {"rating": value, "label": label}
                for value, label in (
                    (1, "Very poor"),
                    (2, "Poor"),
                    (3, "Okay"),
                    (4, "Good"),
                    (5, "Excellent"),
                )
            ],
        }

    result = SupportService.submit_rating(order.id, req.rating, req.feedback)
    return {
        "success": result.get("success", False),
        "orderId": order.id,
        "rating": req.rating,
        "feedback": req.feedback,
        "message": result.get("msg", "Thanks for the feedback"),
    }
