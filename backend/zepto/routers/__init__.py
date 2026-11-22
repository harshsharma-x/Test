"""Routers exposing the documented Zepto endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter

from backend.zepto.routers.account import router as account_router
from backend.zepto.routers.auth import router as auth_router
from backend.zepto.routers.cart import router as cart_router
from backend.zepto.routers.catalogue import router as catalogue_router
from backend.zepto.routers.coupons import router as coupons_router
from backend.zepto.routers.graphql import router as graphql_router
from backend.zepto.routers.orders import router as orders_router
from backend.zepto.routers.payment import router as payment_router
from backend.zepto.routers.search import router as search_router
from backend.zepto.routers.coupons import router as coupons_router


def all_routers() -> List[APIRouter]:
    """Every Zepto-compatible router, in mount order."""
    return [
        auth_router,
        catalogue_router,
        search_router,
        cart_router,
        coupons_router,
        payment_router,
        orders_router,
        account_router,
        graphql_router,
    ]
