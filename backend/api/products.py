"""Products API: Catalogue pages, categories, product details, buy-again."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.database.models import Product


class ProductService:
    @staticmethod
    def get_page(
        db: Session,
        latitude: float = 19.0760,
        longitude: float = 72.8777,
        page_type: str = "HOME",
        page_size: int = 30,
    ) -> Dict[str, Any]:
        """Catalogue layout matching GET /lms/api/v2/get_page."""
        products = db.query(Product).filter(Product.availability == True).limit(page_size).all()
        categories = list(dict.fromkeys(p.category for p in products))

        widgets: List[Dict[str, Any]] = [
            {
                "widgetType": "HERO_BANNER",
                "title": "Superfast 10-Minute Delivery",
                "subtitle": "Fresh Groceries & Essentials at Wholesale Prices",
                "imageUrl": "https://cdn.zeptonow.com/production/ik-seo/tr:w-1200,cm-pad_resize/cms/banner/super_savings.jpg",
            },
            {
                "widgetType": "CATEGORY_GRID",
                "title": "Explore by Category",
                "categories": categories,
            },
            {
                "widgetType": "PRODUCT_CAROUSEL",
                "title": "Trending Essentials",
                "products": [
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
                    }
                    for p in products[:6]
                ],
            },
            {
                "widgetType": "PRODUCT_GRID",
                "title": "Popular in Mumbai",
                "products": [
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
                    }
                    for p in products[6:]
                ],
            },
        ]

        return {
            "endOfPage": True,
            "storeServiceableResponse": {
                "serviceable": True,
                "storeId": "store_mum_central_01",
                "isNightlyStore": False,
                "etaMinutes": 10,
            },
            "pageLayout": {
                "widgets": widgets,
                "pageType": page_type,
            },
        }

    @staticmethod
    def get_product_detail(db: Session, product_id: str) -> Optional[Dict[str, Any]]:
        """Product details page info."""
        p = db.query(Product).filter((Product.id == product_id) | (Product.external_product_id == product_id)).first()
        if not p:
            return None
        return {
            "id": p.id,
            "externalProductId": p.external_product_id,
            "name": p.name,
            "brand": p.brand,
            "category": p.category,
            "price": p.price,
            "originalPrice": p.original_price,
            "discountPercent": p.discount_percent,
            "unit": p.unit,
            "imageUrl": p.image_url,
            "availability": p.availability,
            "stockQuantity": p.stock_quantity,
            "rating": p.rating,
            "description": p.description or f"High quality {p.name} delivered in 10 minutes.",
            "tags": ["Super Saver", "Express 10m"],
        }

    @staticmethod
    def get_buy_again(db: Session, account_id: str) -> Dict[str, Any]:
        """Buy again recommendations matching GET /recommendation-service/api/v1/buy-again-products."""
        products = db.query(Product).limit(4).all()
        return {
            "storeProducts": [
                {
                    "id": p.id,
                    "name": p.name,
                    "price": p.price,
                    "originalPrice": p.original_price,
                    "discountPercent": p.discount_percent,
                    "unit": p.unit,
                    "imageUrl": p.image_url,
                }
                for p in products
            ]
        }
