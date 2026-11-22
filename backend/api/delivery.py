"""Delivery API: Live tracking, delivery ETA, rider status."""
from __future__ import annotations

from typing import Any, Dict


class DeliveryService:
    @staticmethod
    def get_eta(latitude: float, longitude: float) -> Dict[str, Any]:
        return {
            "etaMinutes": 10,
            "trafficStatus": "NORMAL",
            "darkStoreName": "Zepto Mumbai Hub 12",
            "distanceKm": 1.2,
        }

    @staticmethod
    def get_live_tracking(order_id: str) -> Dict[str, Any]:
        return {
            "orderId": order_id,
            "rider": {
                "name": "Ramesh Kumar",
                "phone": "+91 XXXXX 91234",
                "vehicle": "Electric Scooter (MH02-DE-1234)",
                "rating": 4.9,
            },
            "currentEtaMinutes": 7,
            "status": "Rider on the way",
            "coordinates": {"lat": 19.0720, "lng": 72.8750},
        }
