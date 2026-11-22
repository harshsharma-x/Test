"""Search API: Product query search, autocomplete suggestions, category/brand filters."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.database.models import Product


class SearchService:
    @staticmethod
    def search_products(
        db: Session,
        query: str,
        category: Optional[str] = None,
        sort_by: Optional[str] = None,  # price_asc, price_desc, discount, popular
        page: int = 0,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Search products matching POST /user-search-service/api/v3/search."""
        q = query.strip()
        db_query = db.query(Product)
        if q:
            search_pattern = f"%{q}%"
            db_query = db_query.filter(
                or_(
                    Product.name.ilike(search_pattern),
                    Product.brand.ilike(search_pattern),
                    Product.category.ilike(search_pattern),
                )
            )

        if category and category != "All":
            db_query = db_query.filter(Product.category == category)

        if sort_by == "price_asc":
            db_query = db_query.order_by(Product.price.asc())
        elif sort_by == "price_desc":
            db_query = db_query.order_by(Product.price.desc())
        elif sort_by == "discount":
            db_query = db_query.order_by(Product.discount_percent.desc())
        else:
            db_query = db_query.order_by(Product.rating.desc())

        total_count = db_query.count()
        items = db_query.offset(page * page_size).limit(page_size).all()

        return {
            "query": query,
            "pageNumber": page,
            "totalCount": total_count,
            "items": [
                {
                    "id": p.id,
                    "name": p.name,
                    "brand": p.brand,
                    "category": p.category,
                    "price": p.price,
                    "originalPrice": p.original_price,
                    "discountPercent": p.discount_percent,
                    "unit": p.unit,
                    "imageUrl": p.image_url,
                    "rating": p.rating,
                    "availability": p.availability,
                    "stockQuantity": p.stock_quantity,
                }
                for p in items
            ],
            "facets": {
                "categories": [c[0] for c in db.query(Product.category).distinct().all()],
                "brands": [b[0] for b in db.query(Product.brand).distinct().all() if b[0]],
            },
        }

    @staticmethod
    def get_suggestions(db: Session, query: str) -> List[str]:
        """Search query autocomplete suggestions."""
        q = query.strip()
        if not q:
            return ["Milk", "Mangoes", "Chips", "Chocolate", "Coffee", "Noodles"]
        results = (
            db.query(Product.name)
            .filter(Product.name.ilike(f"%{q}%"))
            .limit(6)
            .all()
        )
        return [r[0] for r in results]
