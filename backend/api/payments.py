"""Payments API: Payment method listings, QuickPay integration, authorized handoff."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List


class PaymentService:
    @staticmethod
    def get_payment_methods(amount: float) -> List[Dict[str, Any]]:
        """Available payment options matching POST /payment-service/payment-listing-api/v1/quickpay."""
        return [
            {
                "id": "upi",
                "name": "UPI (Google Pay, PhonePe, Paytm)",
                "type": "UPI",
                "icon": "Smartphone",
                "isRecommended": True,
                "description": "Instant payment via UPI App",
            },
            {
                "id": "cards",
                "name": "Credit / Debit Cards",
                "type": "CARD",
                "icon": "CreditCard",
                "isRecommended": False,
                "description": "Visa, Mastercard, RuPay (Secure 3D Handoff)",
            },
            {
                "id": "wallet",
                "name": "Zepto Wallet / PayLater",
                "type": "WALLET",
                "icon": "Wallet",
                "isRecommended": False,
                "description": "Available Balance: ₹50.00",
            },
            {
                "id": "cod",
                "name": "Cash on Delivery",
                "type": "COD",
                "icon": "Banknote",
                "isRecommended": False,
                "description": "Pay cash/UPI to delivery partner at doorstep",
            },
        ]

    @staticmethod
    def initiate_payment_handoff(
        account_id: str,
        amount: float,
        payment_method: str,
    ) -> Dict[str, Any]:
        """Creates a secure authorized payment reference. Never stores card details."""
        txn_id = f"txn_{uuid.uuid4().hex[:12]}"
        return {
            "success": True,
            "transactionId": txn_id,
            "amount": amount,
            "paymentMethod": payment_method,
            "status": "AUTHORIZED",
            "redirectUrl": f"/payment/verify?txn={txn_id}&amount={amount}",
        }
