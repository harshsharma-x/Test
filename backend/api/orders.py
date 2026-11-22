"""Orders API: Order placement, order history, details, cancellations."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.api.cart import CartService
from backend.api.checkout import CheckoutService
from backend.database.models import Order


class OrderService:
    @staticmethod
    def create_order(
        db: Session,
        account_id: str,
        payment_method: str = "UPI",
        address_id: Optional[str] = None,
        coupon_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Places a verified order after checkout validation, and clears the cart."""
        summary = CheckoutService.get_checkout_summary(db, account_id, coupon_code, address_id)
        if not summary.get("valid"):
            return {"success": False, "error": summary.get("error", "Invalid checkout state")}

        cart_info = summary["cart"]
        breakdown = summary["billBreakdown"]
        addr = summary.get("selectedAddress")
        addr_str = f"{addr.get('flatDetails', '')}, {addr.get('buildingName', '')}, {addr.get('city', '')} - {addr.get('pincode', '')}" if addr else "Default Saved Address"

        order_id = str(uuid.uuid4())
        external_code = f"ZPT{uuid.uuid4().hex[:8].upper()}"

        new_order = Order(
            id=order_id,
            account_id=account_id,
            external_order_id=external_code,
            status="PLACED",
            total_amount=breakdown["finalPayable"],
            discount_amount=breakdown["couponDiscount"] + breakdown["itemDiscount"],
            delivery_fee=breakdown["effectiveDeliveryFee"],
            items_json=json.dumps(cart_info["items"]),
            delivery_address=addr_str,
            eta_minutes=10,
            created_at=datetime.utcnow(),
        )
        db.add(new_order)
        db.commit()

        # Clear cart upon order creation
        CartService.clear_cart(db, account_id)

        return {
            "success": True,
            "order": {
                "id": new_order.id,
                "orderCode": new_order.external_order_id,
                "status": new_order.status,
                "totalAmount": new_order.total_amount,
                "discountAmount": new_order.discount_amount,
                "itemCount": cart_info["itemCount"],
                "etaMinutes": new_order.eta_minutes,
                "deliveryAddress": new_order.delivery_address,
                "placedAt": new_order.created_at.isoformat(),
            },
        }

    @staticmethod
    def list_orders(db: Session, account_id: str) -> List[Dict[str, Any]]:
        """Order history matching GET /api/v2/order/."""
        orders = (
            db.query(Order)
            .filter(Order.account_id == account_id)
            .order_by(Order.created_at.desc())
            .all()
        )
        return [
            {
                "id": o.id,
                "orderCode": o.external_order_id,
                "status": o.status,
                "totalAmount": o.total_amount,
                "discountAmount": o.discount_amount,
                "items": json.loads(o.items_json) if o.items_json else [],
                "deliveryAddress": o.delivery_address,
                "etaMinutes": o.eta_minutes,
                "placedAt": o.created_at.isoformat(),
            }
            for o in orders
        ]

    @staticmethod
    def get_order_details(db: Session, order_id: str) -> Optional[Dict[str, Any]]:
        """Order details matching POST /pfs-postorder/api/v1/get-page/ORDER_DETAILS."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None

        items = json.loads(order.items_json) if order.items_json else []
        return {
            "id": order.id,
            "orderCode": order.external_order_id,
            "status": order.status,
            "totalAmount": order.total_amount,
            "discountAmount": order.discount_amount,
            "deliveryFee": order.delivery_fee,
            "deliveryAddress": order.delivery_address,
            "etaMinutes": order.eta_minutes,
            "items": items,
            "itemQuantityCount": sum(it.get("quantity", 1) for it in items),
            "placedTime": order.created_at.isoformat(),
            "trackingSteps": [
                {"label": "Order Placed", "completed": True, "time": order.created_at.strftime("%I:%M %p")},
                {"label": "Packed at Dark Store", "completed": order.status in ["PACKING", "OUT_FOR_DELIVERY", "DELIVERED"]},
                {"label": "Out for Delivery", "completed": order.status in ["OUT_FOR_DELIVERY", "DELIVERED"]},
                {"label": "Delivered", "completed": order.status == "DELIVERED"},
            ],
        }

    @staticmethod
    def cancel_order(db: Session, order_id: str, reason: str = "Customer request") -> Dict[str, Any]:
        """Cancel an ongoing order if eligible."""
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"success": False, "error": "Order not found"}
        if order.status in ["DELIVERED", "CANCELLED"]:
            return {"success": False, "error": f"Order already {order.status.lower()}"}

        order.status = "CANCELLED"
        db.commit()
        return {"success": True, "status": "CANCELLED", "orderId": order.id}
