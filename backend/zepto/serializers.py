"""Serializers producing Zepto's documented payload shapes from our models.

Every money field emitted here is an integer number of paise, matching the
captured payloads (`productVariant.mrp`, `grandTotalAmount`, ...).
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional

from backend.database.models import Offer, Order, Product
from backend.zepto.constants import CDN_BASE, DEFAULT_STORE_ID, FREE_DELIVERY_THRESHOLD_RUPEES
from backend.zepto.money import to_paise

_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

_UNIT_RE = re.compile(r"([\d.]+)\s*(kg|gms|g|ml|ltr|l|pcs|pc)\b", re.IGNORECASE)
_WEIGHT_RANK = {"KG": 0, "LITER": 0, "GMS": 1, "ML": 1, "PIECE": 2}


def stable_id(*parts: str) -> str:
    """Deterministic UUID for entities the captures identify by UUID."""
    return str(uuid.uuid5(_NAMESPACE, "|".join(str(p) for p in parts)))


def _parse_unit(unit: str) -> tuple[int, str]:
    """'350 g' -> (350, 'GMS'); prefers weight/volume over piece counts."""
    best: Optional[tuple[float, str]] = None
    for raw_value, raw_unit in _UNIT_RE.findall(unit or ""):
        try:
            value = float(raw_value)
        except ValueError:
            continue
        unit_key = raw_unit.lower()
        if unit_key in ("kg",):
            candidate = (value * 1000.0, "KG")
        elif unit_key in ("l", "ltr"):
            candidate = (value * 1000.0, "LITER")
        elif unit_key in ("g", "gms"):
            candidate = (value, "GMS")
        elif unit_key == "ml":
            candidate = (value, "ML")
        else:
            candidate = (value, "PIECE")
        if best is None or _WEIGHT_RANK[candidate[1]] < _WEIGHT_RANK[best[1]]:
            best = candidate

    if best is None:
        return 1, "PIECE"
    return int(round(best[0])), best[1]


def _image_payload(product: Product) -> Dict[str, Any]:
    """Builds the CMS image object; `path` stays relative when derivable."""
    url = product.image_url or ""
    marker = "cm-pad_resize/"
    path = url.split(marker, 1)[1] if marker in url else url
    filename = path.rsplit("/", 1)[-1] if path else f"{product.id}.png"
    return {
        "id": stable_id("image", product.id),
        "name": filename,
        "path": path,
        "lottiePath": None,
        "videoPath": None,
        "mediaType": "IMAGE",
        "width": 1334,
        "height": 1334,
        "hidePadding": True,
        "relativePath": None,
    }


def product_payload(product: Product) -> Dict[str, Any]:
    """The nested `product` object of a storeProduct."""
    category_id = stable_id("category", product.category)
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand or "Zepto",
        "imported": False,
        "countryOfOrigin": "India",
        "minimumRequiredAge": 0,
        "discountApplicable": product.discount_percent > 0,
        "searchKeywords": [],
        "howToUse": [],
        "ingredients": "",
        "manufacturerName": product.brand or "Zepto",
        "manufacturerAddress": "",
        "description": [product.description] if product.description else [],
        "l3CategoryIds": [category_id],
        "prioritisedSearchKeywords": [],
        "primarySubcategory": category_id,
        "brandId": stable_id("brand", product.brand or "Zepto"),
        "rawTitle": "",
        "l3CategoryDetails": {"id": category_id, "name": product.category},
    }


def variant_payload(product: Product) -> Dict[str, Any]:
    """The nested `productVariant` object of a storeProduct."""
    weight, unit_of_measure = _parse_unit(product.unit or "")
    return {
        "id": stable_id("variant", product.id),
        "quantity": 1,
        "mrp": to_paise(product.original_price),
        "packsize": 1,
        "weightInGms": weight,
        "unitOfMeasure": unit_of_measure,
        "formattedPacksize": product.unit or "1 pc",
        "images": [_image_payload(product)],
        "availableQuantity": product.stock_quantity,
        "isAvailable": bool(product.availability and product.stock_quantity > 0),
        "rating": product.rating,
    }


def store_product(
    product: Product,
    cart_quantity: int = 0,
    store_id: str = DEFAULT_STORE_ID,
) -> Dict[str, Any]:
    """A storeProduct as returned by get_page, search, and buy-again."""
    discount_amount = max(product.original_price - product.price, 0.0)
    return {
        "objectId": product.id,
        "id": product.id,
        "storeId": store_id,
        "product": product_payload(product),
        "productVariant": variant_payload(product),
        "discountedSellingPrice": to_paise(product.price),
        "mrp": to_paise(product.original_price),
        "discountPercent": product.discount_percent,
        "discountAmount": to_paise(discount_amount),
        "storeProductDiscountId": stable_id("discount", product.id) if discount_amount > 0 else None,
        "availableQuantity": product.stock_quantity,
        "quantity": cart_quantity,
        "allocatedQuantity": 0,
        "isAvailable": bool(product.availability and product.stock_quantity > 0),
        "category": product.category,
    }


def cart_product(
    product: Product,
    quantity: int,
    cart_product_id: str,
    store_id: str = DEFAULT_STORE_ID,
) -> Dict[str, Any]:
    """A storeProduct enriched with the line-item fields a cart carries."""
    payload = store_product(product, cart_quantity=quantity, store_id=store_id)
    payload["cartProductId"] = cart_product_id
    payload["quantity"] = quantity
    payload["lineTotal"] = to_paise(product.price * quantity)
    payload["lineMrpTotal"] = to_paise(product.original_price * quantity)
    return payload


def coupon_payload(offer: Offer, cart_total_rupees: float) -> Dict[str, Any]:
    """An applicable coupon entry, as bulk-widget-data returns them."""
    from backend.api.offers import OfferService

    is_eligible = cart_total_rupees >= offer.min_cart_value
    discount = OfferService.compute_discount(offer, cart_total_rupees) if is_eligible else 0.0
    amount_needed = max(0.0, offer.min_cart_value - cart_total_rupees)

    return {
        "id": offer.id,
        "couponId": offer.id,
        "code": offer.code,
        "title": offer.title,
        "description": offer.description or "",
        "offerType": offer.offer_type,
        "discountValue": to_paise(offer.discount_value),
        "minCartValue": to_paise(offer.min_cart_value),
        "maxDiscount": to_paise(offer.max_discount) if offer.max_discount else None,
        "isEligible": is_eligible,
        "potentialDiscount": to_paise(discount),
        "amountNeeded": to_paise(amount_needed),
        "isFreeDelivery": offer.offer_type == "FREE_DELIVERY",
    }


def cart_bill(
    cart_details: Dict[str, Any],
    items: List[Dict[str, Any]],
    coupons: Optional[List[Dict[str, Any]]] = None,
    coupon_code: Optional[str] = None,
    coupon_discount_rupees: float = 0.0,
) -> Dict[str, Any]:
    """Cart totals in the shape `/cfs/api/v1/cart/create` returns."""
    cart_total = float(cart_details.get("cartTotal", 0.0))
    mrp_total = float(cart_details.get("mrpTotal", 0.0))
    delivery_fee = float(cart_details.get("deliveryFee", 0.0))
    threshold = FREE_DELIVERY_THRESHOLD_RUPEES
    handling = 4.0 if items else 0.0
    payable = max(0.0, cart_total - coupon_discount_rupees) + delivery_fee + handling

    return {
        "cartId": cart_details.get("cartId"),
        "storeId": DEFAULT_STORE_ID,
        "itemsCount": cart_details.get("itemCount", 0),
        "totalMrp": to_paise(mrp_total),
        "totalSellingPrice": to_paise(cart_total),
        "totalDiscount": to_paise(max(mrp_total - cart_total, 0.0)),
        "deliveryFee": to_paise(delivery_fee),
        "deliveryFeeMov": to_paise(cart_details.get("amountNeededForFreeDelivery", 0.0)),
        "freeDeliveryThreshold": to_paise(threshold),
        "handlingFee": to_paise(handling),
        "couponDiscount": to_paise(coupon_discount_rupees),
        "appliedCouponCode": coupon_code,
        "totalPayable": to_paise(payable),
        "etaMinutes": 10,
        "isFreeDelivery": delivery_fee <= 0.0,
        "cartProducts": items,
        "applicableCoupons": coupons or [],
    }


def _order_items(order: Order) -> List[Dict[str, Any]]:
    if not order.items_json:
        return []
    try:
        return json.loads(order.items_json)
    except (TypeError, ValueError):
        return []


def _product_name_row(item: Dict[str, Any]) -> Dict[str, Any]:
    """productsNamesAndCounts entry for the order list."""
    product_id = item.get("productId") or stable_id("item", str(item.get("name", "")))
    image_url = item.get("imageUrl") or ""
    marker = "cm-pad_resize/"
    path = image_url.split(marker, 1)[1] if marker in image_url else image_url
    filename = path.rsplit("/", 1)[-1] if path else f"{product_id}.png"
    return {
        "name": item.get("name"),
        "count": item.get("quantity", 1),
        "id": product_id,
        "image": {
            "id": stable_id("image", product_id),
            "name": filename,
            "path": path,
            "lottiePath": None,
            "videoPath": None,
            "mediaType": "IMAGE",
            "width": 1334,
            "height": 1334,
            "hidePadding": True,
            "relativePath": None,
        },
        "icon": None,
        "productVariantId": item.get("productId") or stable_id("variant", product_id),
        "reorder": True,
    }


def order_summary(order: Order) -> Dict[str, Any]:
    """One element of `GET /api/v2/order/` -> orders[]."""
    items = _order_items(order)
    placed = order.created_at.isoformat() + "Z" if order.created_at else None
    return {
        "id": order.id,
        "code": order.external_order_id,
        "status": order.status,
        "formattedStatus": order.status.replace("_", " "),
        "paymentStatus": order.payment_status,
        "paymentMethod": order.payment_method,
        "itemQuantityCount": sum(int(it.get("quantity", 1)) for it in items),
        "grandTotalAmount": to_paise(order.total_amount),
        "totalRefundAmount": 0,
        "placedTime": placed,
        "rating": None,
        "ratingSkipped": False,
        "totalDeliveryTimeInSeconds": None,
        "totalArrivalTimeInSeconds": None,
        "storeId": DEFAULT_STORE_ID,
        "etaMinutes": order.eta_minutes,
        "productsNamesAndCounts": [_product_name_row(it) for it in items],
    }


def order_detail(order: Order) -> Dict[str, Any]:
    """Payload for `pfs-postorder .../get-page/ORDER_DETAILS`."""
    items = _order_items(order)
    placed = order.created_at.isoformat() + "Z" if order.created_at else None
    timeline = [
        {"label": "Order Placed", "completed": True, "time": order.created_at.strftime("%I:%M %p") if order.created_at else None},
        {"label": "Packed at Dark Store", "completed": order.status in ("PACKING", "OUT_FOR_DELIVERY", "DELIVERED")},
        {"label": "Out for Delivery", "completed": order.status in ("OUT_FOR_DELIVERY", "DELIVERED")},
        {"label": "Delivered", "completed": order.status == "DELIVERED"},
    ]
    return {
        "orderDetails": {
            "id": order.id,
            "code": order.external_order_id,
            "status": order.status,
            "formattedStatus": order.status.replace("_", " "),
            "placedTime": placed,
            "etaMinutes": order.eta_minutes,
            "itemQuantityCount": sum(int(it.get("quantity", 1)) for it in items),
            "storeId": DEFAULT_STORE_ID,
            "timeline": timeline,
        },
        "itemBreakdown": [
            {
                "name": it.get("name"),
                "quantity": it.get("quantity", 1),
                "unit": it.get("unit"),
                "unitPrice": to_paise(it.get("price", 0)),
                "lineTotal": to_paise(it.get("total", 0)),
                "imageUrl": it.get("imageUrl"),
            }
            for it in items
        ],
        "deliveryAddress": {"formattedAddress": order.delivery_address},
        "paymentSummary": {
            "paymentMethod": order.payment_method,
            "paymentStatus": order.payment_status,
            "transactionReference": order.transaction_reference,
            "grandTotalAmount": to_paise(order.total_amount),
            "totalDiscount": to_paise(order.discount_amount),
            "deliveryFee": to_paise(order.delivery_fee),
        },
    }
