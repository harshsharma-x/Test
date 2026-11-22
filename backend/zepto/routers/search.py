"""Search router.

Documented endpoints
    POST /user-search-service/api/v3/search
    POST /user-search-service/api/v3/search/filters
    GET  /search-federator-service/api/v1/search   (fallback used by web)

Autocomplete is exposed on the federator path style as well.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.search import SearchService
from backend.database.connection import get_db
from backend.database.models import Product
from backend.zepto.constants import DEFAULT_STORE_ID
from backend.zepto.deps import AuthContext, optional_auth
from backend.zepto.routers.catalogue import _cart_quantities
from backend.zepto.serializers import store_product

router = APIRouter(tags=["Search"])


class SearchRequest(BaseModel):
    """Body shared by /search and /search/filters."""

    query: str = ""
    pageNumber: int = 0
    mode: str = "SHOW_ALL_RESULTS"
    userSessionId: Optional[str] = None
    filters: Dict[str, Any] = Field(default_factory=dict)


def _matches(db: Session, req: SearchRequest) -> List[Product]:
    """Applies query + facet filters and returns the page of products."""
    pattern = f"%{req.query.strip()}%"
    query = db.query(Product)
    if req.query.strip():
        query = query.filter(
            Product.name.ilike(pattern)
            | Product.brand.ilike(pattern)
            | Product.category.ilike(pattern)
        )

    selected_category = req.filters.get("category")
    if selected_category and selected_category != "All":
        query = query.filter(Product.category == selected_category)

    selected_brand = req.filters.get("brand")
    if selected_brand:
        query = query.filter(Product.brand == selected_brand)

    sort_by = req.filters.get("sortBy", "popular")
    if sort_by == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort_by == "discount":
        query = query.order_by(Product.discount_percent.desc())
    else:
        query = query.order_by(Product.rating.desc())

    page_size = 24
    return query.offset(req.pageNumber * page_size).limit(page_size).all()


def _facets(db: Session) -> Dict[str, List[str]]:
    categories = [row[0] for row in db.query(Product.category).distinct().all()]
    brands = [row[0] for row in db.query(Product.brand).distinct().all() if row[0]]
    return {"categories": categories, "brands": brands}


def _search_payload(
    db: Session,
    req: SearchRequest,
    account_id: Optional[str],
) -> Dict[str, Any]:
    products = _matches(db, req)
    quantities = _cart_quantities(db, account_id)
    facets = _facets(db)

    store_products = [
        store_product(p, quantities.get(p.id, 0), store_id=DEFAULT_STORE_ID)
        for p in products
    ]

    filters = [
        {
            "id": "category",
            "label": "Category",
            "options": [
                {"id": name, "label": name, "selected": req.filters.get("category") == name}
                for name in facets["categories"]
            ],
        },
        {
            "id": "brand",
            "label": "Brand",
            "options": [
                {"id": name, "label": name, "selected": req.filters.get("brand") == name}
                for name in facets["brands"]
            ],
        },
    ]

    return {
        "query": req.query,
        "pageNumber": req.pageNumber,
        "mode": req.mode,
        "totalCount": len(products),
        "products": store_products,
        "storeProducts": store_products,
        "layout": [
            {
                "widgetId": "search-results",
                "widgetType": "PRODUCT_GRID",
                "title": f"Results for \u201c{req.query}\u201d" if req.query else "All Products",
                "data": {"storeProducts": store_products},
            }
        ],
        "filters": filters,
        "facets": facets,
        "nextPageParams": None,
        "endOfPage": len(products) < 24,
    }


@router.post("/user-search-service/api/v3/search")
def search_v3(
    req: SearchRequest,
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(optional_auth),
) -> Dict[str, Any]:
    """Primary product search used by the web client."""
    return _search_payload(db, req, ctx.account_id if ctx else None)


@router.post("/user-search-service/api/v3/search/filters")
def search_filters_v3(
    req: SearchRequest,
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(optional_auth),
) -> Dict[str, Any]:
    """Same search, scoped to the filter bottom sheet."""
    payload = _search_payload(db, req, ctx.account_id if ctx else None)
    return {
        "filters": payload["filters"],
        "facets": payload["facets"],
        "totalCount": payload["totalCount"],
    }


@router.get("/search-federator-service/api/v1/search")
def search_federator(
    query: str = "",
    pageNumber: int = 0,
    mode: str = "SHOW_ALL_RESULTS",
    db: Session = Depends(get_db),
    ctx: Optional[AuthContext] = Depends(optional_auth),
) -> Dict[str, Any]:
    """GET fallback the web client uses when the v3 endpoint is unavailable."""
    return _search_payload(
        db,
        SearchRequest(query=query, pageNumber=pageNumber, mode=mode),
        ctx.account_id if ctx else None,
    )


@router.get("/search-federator-service/api/v1/autocomplete")
def autocomplete(query: str = "", db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Typeahead suggestions for the search bar."""
    suggestions = SearchService.get_suggestions(db, query)
    return {"query": query, "suggestions": suggestions}
