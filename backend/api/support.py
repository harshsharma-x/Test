"""Support API: Order ratings (Samiksha service), FAQs, Help tickets."""
from __future__ import annotations

from typing import Any, Dict, List


class SupportService:
    @staticmethod
    def get_faq_topics() -> List[Dict[str, str]]:
        return [
            {"topic": "Where is my order?", "answer": "You can track your order in real-time under Orders > Track Order."},
            {"topic": "How do offers work?", "answer": "Click 'Auto Apply Best Offer' in your cart to automatically select the coupon maximizing your discount."},
            {"topic": "Multi-Account switching", "answer": "Switch between your personal and secondary accounts instantly via the top Account Switcher."},
            {"topic": "Refunds and Cancellation", "answer": "Orders can be cancelled before dispatch for an immediate refund to your original payment method."},
        ]

    @staticmethod
    def submit_rating(order_id: str, rating: int, feedback: str = "") -> Dict[str, Any]:
        """Submit feedback matching POST /samiksha-service/api/v1/order-rating."""
        return {
            "success": True,
            "orderId": order_id,
            "rating": rating,
            "msg": "Thank you for rating your delivery experience!",
        }
