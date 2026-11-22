"""Cart router.

Documented endpoints
    POST /cfs/api/v1/cart/create     - authoritative full-cart sync

Supporting endpoints for the web client
    GET  /cfs/api/v1/cart            - current server cart
    POST /cfs/api/v1/cart/add        - increment one product
    POST /cfs/api/v1/cart/update     - set an exact quantity
    POST /cfs/api/v1/cart/remove     - drop a product
    POST /cfs/api/v1/cart/clear      - empty the cart
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.zepto.cart_view import (
    add_product,
    build_cart_payload,
    clear_cart,
    replace_cart,
    set_quantity,
)
from backend.zepto.constants import DEFAULT_LATITUDE, DEFAULT_STORE_ID
from backend.zepto.deps import AuthContext, require_auth

router = APIRouter(tags=["Cart"])


class DeliveryInstructions(BaseModel):
    """Doorstep notes carried by the documented cart body."""

    leaveAtGate: bool = False
    doNotRingBell: bool = False
    bewareOfPets: bool = False
    returnPaperBag: bool = False
    returnCokePetBottle: bool = False


class CartProductEntry(BaseModel):
    """One line of `cartProducts` in the cart/create body."""

    storeProductId: str
    quantity: int = 1
    productVariantId: Optional[str] = None
    mrp: Optional[int] = None
    isDiscountApplicable: bool = True
    isAddedToGiftBag: bool = False
    cartProductId: Optional[str] = None


class CartCreateRequest(BaseModel):
    """Body of POST /cfs/api/v1/cart/create."""

    storeId: str = DEFAULT_STORE_ID
    cartId: Optional[str] = None
    cartProducts: List[CartProductEntry] = Field(default_factory=list)
    cartProductsV2: List[CartProductEntry] = Field(default_factory=list)
    deliveryInstructions: DeliveryInstructions = Field(default_factory=DeliveryInstructions)
    riderTip: float = 0
    latitude: float = DEFAULT_LATITUDE
    swappedPvIds: Dict[str, Any] = Field(default_factory=dict)
    removedCampaignProducts: List[Any] = Field(default_factory=list)
    availedCampaignProducts: List[Any] = Field(default_factory=list)
    availedCampaignProductIds: List[Any] = Field(default_factory=list)
    oosProductMeta: List[Any] = Field(default_factory=list)


class CartProductAction(BaseModel):
    """Body for the single-product cart helpers."""

    storeProductId: str
    quantity: int = 1


def _entries(req: CartCreateRequest) -> List[Dict[str, Any]]:
    """Prefers cartProductsV2 (the richer superset) when the client sends it."""
    source = req.cartProductsV2 or req.cartProducts
    return [entry.model_dump() for entry in source]


@router.get("/cfs/api/v1/cart")
def get_cart(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the account's persisted cart with live totals."""
    return build_cart_payload(db, ctx.account_id)


@router.post("/cfs/api/v1/cart/create")
def create_cart(
    req: CartCreateRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Syncs the server cart to the client's cart, then returns enriched totals."""
    rejected = replace_cart(db, ctx.account_id, _entries(req))
    payload = build_cart_payload(db, ctx.account_id)
    payload["rejectedProducts"] = rejected
    payload["deliveryInstructions"] = req.deliveryInstructions.model_dump()
    return payload


@router.post("/cfs/api/v1/cart/add")
def add_to_cart(
    req: CartProductAction,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Adds `quantity` units of one product to the cart."""
    result = add_product(db, ctx.account_id, req.storeProductId, req.quantity)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return build_cart_payload(db, ctx.account_id)


@router.post("/cfs/api/v1/cart/update")
def update_cart_quantity(
    req: CartProductAction,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Sets an exact quantity for one product; 0 removes it."""
    result = set_quantity(db, ctx.account_id, req.storeProductId, req.quantity)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return build_cart_payload(db, ctx.account_id)


@router.post("/cfs/api/v1/cart/remove")
def remove_from_cart(
    req: CartProductAction,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Removes a product from the cart entirely."""
    result = set_quantity(db, ctx.account_id, req.storeProductId, 0)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return build_cart_payload(db, ctx.account_id)


@router.post("/cfs/api/v1/cart/clear")
def empty_cart(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Empties the cart and drops any applied coupon."""
    clear_cart(db, ctx.account_id)
    return build_cart_payload(db, ctx.account_id)
