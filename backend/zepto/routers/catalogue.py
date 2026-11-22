"""Catalogue router.

Documented endpoints
    GET  /lms/api/v2/get_page
    POST /cfs/api/v1/bulk-widget-data
    GET  /recommendation-service/api/v1/buy-again-products
    GET  /serviceability-service/api/v1/serviceability
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import Offer, Order, Product, ShoppingCart, ShoppingCartItem
from backend.zepto.constants import DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_STORE_ID
from backend.zepto.deps import AuthContext, optional_auth
from backend.zepto.money import to_paise
from backend.zepto.serializers import coupon_payload, stable_id, store_product

router = APIRouter(tags=["Catalogue"])

BOTTOM_NAV = [
    {"id": "HOME", "label": "Home", "deeplinkUrl": "/home"},
    {"id": "CATEGORIES", "label": "Categories", "deeplinkUrl": "/categories"},
    {"id": "OFFERS", "label": "Offers", "deeplinkUrl": "/offers"},
    {"id": "ORDERS", "label": "Orders", "deeplinkUrl": "/orders"},
    {"id": "ACCOUNT", "label": "Account", "deeplinkUrl": "/account"},
]


class BulkWidgetRequest(BaseModel):
    """Body of POST /cfs/api/v1/bulk-widget-data."""

    widgets: List[Dict[str, Any]] = Field(default_factory=list)
    cartProducts: List[Dict[str, Any]] = Field(default_factory=list)
    cartId: Optional[str] = None
    enrichCall: bool = True
    showAllOffers: bool = False
    couponIds: List[str] = Field(default_factory=list)
    campaignIds: List[str] = Field(default_factory=list)


def _cart_quantities(db: Session, account_id: Optional[str]) -> Dict[str, int]:
    """Maps product_id -> quantity for the active account's cart."""
    if not account_id:
        return {}
    cart = db.query(ShoppingCart).filter(ShoppingCart.account_id == account_id).first()
    if not cart:
        return {}
    rows = db.query(ShoppingCartItem).filter(ShoppingCartItem.cart_id == cart.id).all()
    return {row.product_id: row.quantity for row in rows}


def _hero_widget() -> Dict[str, Any]:
    return {
        "widgetId": "hero-banner",
        "widgetName": "Hero_Banner_v2",
        "widgetType": "HERO_BANNER",
        "title": "Superfast 10-Minute Delivery",
        "data": {
            "subtitle": "Fresh groceries, snacks and essentials at dark-store prices.",
            "ctaLabel": "Shop all groceries",
            "deeplinkUrl": "/categories",
        },
    }


def _category_widget(products: List[Product]) -> Dict[str, Any]:
    seen: List[str] = []
    for product in products:
        if product.category not in seen:
            seen.append(product.category)

    return {
        "widgetId": "category-grid",
        "widgetName": "Category_Grid_v2",
        "widgetType": "CATEGORY_GRID",
        "title": "Explore by Category",
        "data": {
            "categories": [
                {
                    "id": stable_id("category", name),
                    "name": name,
                    "imageUrl": None,
                    "deeplinkUrl": f"/category/{name}",
                }
                for name in seen
            ]
        },
    }


def _product_widget(
    widget_id: str,
    widget_type: str,
    title: str,
    products: List[Product],
    quantities: Dict[str, int],
) -> Dict[str, Any]:
    return {
        "widgetId": widget_id,
        "widgetName": "Product_Grid_v3",
        "widgetType": widget_type,
        "title": title,
        "data": {
            "storeProducts": [
                store_product(p, quantities.get(p.id, 0)) for p in products
            ]
        },
    }


@router.get("/serviceability-service/api/v1/serviceability")
def check_serviceability(
    lat: float = Query(default=DEFAULT_LATITUDE),
    long: float = Query(default=DEFAULT_LONGITUDE),
) -> Dict[str, Any]:
    """Reports which dark stores can serve the given coordinates."""
    return {
        "errors": [],
        "data": {
            "serviceable": True,
            "addressesData": None,
            "stores": [
                {
                    "serviceable": True,
                    "storeId": DEFAULT_STORE_ID,
                    "storeConstruct": "PRIMARY_STORE",
                    "isNightlyStore": False,
                    "cost": 726.2,
                    "fulfilmentCost": 2178.6,
                    "geofence_area": None,
                }
            ],
            "regionCoordinates": None,
            "primary_store_meta": {"eta_delta_threshold_in_mins": 10},
            "requestedLocation": {"latitude": lat, "longitude": long},
        },
    }


@router.get("/lms/api/v2/get_page")
def get_page(
    latitude: float = DEFAULT_LATITUDE,
    longitude: float = DEFAULT_LONGITUDE,
    page_type: str = "HOME",
    version: str = "v2",
    page_size: int = 30,
    enforce_platform_type: str = "DESKTOP",
    show_new_eta_banner: bool = True,
    last_widget_id: Optional[str] = None,
    layout_id: Optional[str] = None,
    tab_id: Optional[str] = None,
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(optional_auth),
) -> Dict[str, Any]:
    """Returns the LMS layout: widgets, bottom nav, and store serviceability."""
    products = (
        db.query(Product)
        .filter(Product.availability == True)  # noqa: E712
        .limit(max(page_size, 8))
        .all()
    )
    quantities = _cart_quantities(db, ctx.account_id if ctx else None)

    widgets = [
        _hero_widget(),
        _category_widget(products),
        _product_widget("product-carousel-trending", "PRODUCT_CAROUSEL", "Trending Essentials", products[:6], quantities),
        _product_widget("product-grid-popular", "PRODUCT_GRID", "Popular Near You", products, quantities),
    ]

    return {
        "endOfPage": True,
        "storeServiceableResponse": {
            "isNightlyStore": False,
            "secondaryStoreIds": [],
            "serviceable": True,
            "storeId": DEFAULT_STORE_ID,
        },
        "pageLayout": {
            "widgets": widgets,
            "bottomNav": {"default": "HOME", "items": BOTTOM_NAV},
            "headerV2": {
                "defaultBackground": "#F9105E",
                "primaryWidgets": [],
                "secondaryWidgets": [],
                "topNavBarWidget": None,
            },
            "footerV2": {"widget": None},
            "experienceVariant": version,
            "isE2EAdsEnabled": False,
            "isEmiEnabled": False,
            "isListsEnabled": False,
            "isScheduleDeliveryEnabled": False,
            "isYfpEnabled": False,
            "endOfPage": True,
            "pageMeta": {
                "pageType": page_type,
                "platform": enforce_platform_type,
                "showEtaBanner": show_new_eta_banner,
                "tabId": tab_id,
                "layoutId": layout_id,
                "lastWidgetId": last_widget_id,
            },
        },
        "widgets": widgets,
        "bottomNav": BOTTOM_NAV,
        "unserviceableDetails": None,
        "externalVendorServiceabilityInfo": None,
        "festivalUITheme": "",
        "datasource": "lms",
        "passDetails": {},
        "showWalletIconOnHeader": True,
        "nextPageParams": None,
        "storeServiceableResponseV2": [
            {
                "serviceable": True,
                "storeId": DEFAULT_STORE_ID,
                "storeConstruct": "PRIMARY_STORE",
                "isNightlyStore": False,
            }
        ],
        "isEntryPageEnabled": True,
    }


@router.post("/cfs/api/v1/bulk-widget-data")
def bulk_widget_data(
    req: BulkWidgetRequest,
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(optional_auth),
) -> Dict[str, Any]:
    """Enriches widgets with cart state, delivery thresholds, and coupons."""
    from backend.api.cart import CartService

    offers = db.query(Offer).filter(Offer.is_active == True).all()  # noqa: E712
    products = db.query(Product).filter(Product.availability == True).limit(12).all()  # noqa: E712
    quantities = _cart_quantities(db, ctx.account_id if ctx else None)

    cart_total = 0.0
    items_count = 0
    delivery_fee = 0.0
    if ctx:
        details = CartService.get_cart_details(db, ctx.account_id)
        cart_total = float(details["cartTotal"])
        items_count = int(details["itemCount"])
        delivery_fee = float(details["deliveryFee"])

    coupons = [coupon_payload(offer, cart_total) for offer in offers]
    best = max(coupons, key=lambda c: c["potentialDiscount"], default=None)

    widgets: List[Dict[str, Any]] = list(req.widgets or [])
    widgets.append(
        {
            "widgetId": "upsell-strip",
            "widgetName": "Upsell_strip_cfs_homepage_v2",
            "widgetType": "UPSELL_STRIP_WIDGET",
            "data": {
                "couponIds": [c["couponId"] for c in coupons],
                "upsellInfoV3": {
                    "freeDeliveryMov": to_paise(delivery_fee),
                    "bestCouponCode": best["code"] if best else None,
                },
            },
        }
    )
    widgets.append(
        _product_widget(
            "recommended-products",
            "PRODUCT_CAROUSEL",
            "Frequently Bought Together",
            products,
            quantities,
        )
    )

    return {
        "pageLayout": {
            "widgets": widgets,
            "pageMeta": {
                "dynamicWidgetType": "CFS_HOME",
                "deliveryFeeMov": to_paise(delivery_fee),
                "itemsCount": items_count,
                "cartTotal": to_paise(cart_total),
            },
            "endOfPage": True,
        }
    }


@router.get("/recommendation-service/api/v1/buy-again-products")
def buy_again_products(
    store_id: str = DEFAULT_STORE_ID,
    group_id: str = "All Items",
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(optional_auth),
) -> Dict[str, Any]:
    """Products this account ordered before, for one-tap reordering."""
    quantities = _cart_quantities(db, ctx.account_id if ctx else None)

    ordered_ids: List[str] = []
    if ctx:
        orders = (
            db.query(Order)
            .filter(Order.account_id == ctx.account_id)
            .order_by(Order.created_at.desc())
            .limit(10)
            .all()
        )
        for order in orders:
            try:
                for item in json.loads(order.items_json or "[]"):
                    pid = item.get("productId")
                    if pid and pid not in ordered_ids:
                        ordered_ids.append(pid)
            except (TypeError, ValueError):
                continue

    if ordered_ids:
        products = db.query(Product).filter(Product.id.in_(ordered_ids)).all()
    else:
        products = db.query(Product).filter(Product.availability == True).limit(6).all()  # noqa: E712

    return {
        "storeProducts": [
            store_product(p, quantities.get(p.id, 0), store_id=store_id) for p in products
        ],
        "groupNameMapping": {
            "all items": "All Items",
            "dairy products": "Dairy & Breakfast",
            "fruits & vegetables": "Fruits & Vegetables",
            "snacks & drinks": "Snacks & Munchies",
        },
    }
