"""Inventory API: Serviceability, store geofencing, stock checks."""
from __future__ import annotations

from typing import Any, Dict, List
from sqlalchemy.orm import Session

from backend.database.models import Product


class InventoryService:
    @staticmethod
    def check_serviceability(latitude: float, longitude: float) -> Dict[str, Any]:
        """Location serviceability matching GET /serviceability-service/api/v1/serviceability."""
        return {
            "serviceable": True,
            "etaMinutes": 10,
            "stores": [
                {
                    "storeId": "store_primary_01",
                    "storeConstruct": "PRIMARY_STORE",
                    "isNightlyStore": False,
                    "serviceable": True,
                }
            ],
            "primary_store_meta": {
                "eta_delta_threshold_in_mins": 10,
                "surgeApplicable": False,
            },
        }

    @staticmethod
    def check_stock(db: Session, product_ids: List[str]) -> Dict[str, Any]:
        """Verify stock availability for given product IDs."""
        products = db.query(Product).filter(Product.id.in_(product_ids)).all()
        return {
            p.id: {
                "available": p.availability and p.stock_quantity > 0,
                "stockQuantity": p.stock_quantity,
            }
            for p in products
        }
