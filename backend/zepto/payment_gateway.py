"""Payment gateway implementation backed by `payment_transactions`.

Models the two-step flow a real gateway exposes:

    1. initiate -> transaction created in AUTHORIZED (prepaid) or SUCCESS (COD)
    2. confirm  -> prepaid transaction becomes SUCCESS or FAILED

Nothing sensitive is persisted: only the method, the amount, a masked
instrument hint, and the resulting status. Card numbers and UPI PINs never
reach this server.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.database.models import PaymentTransaction
from backend.zepto.constants import PAYMENT_METHODS, PREPAID_METHODS
from backend.zepto.money import format_rupees, to_paise, to_rupees

REFERENCE_PREFIX = "pay"
TRANSACTION_TTL_MINUTES = 15
WALLET_BALANCE_RUPEES = 50.0

METHOD_CATALOGUE: List[Dict[str, Any]] = [
    {
        "id": "UPI",
        "title": "UPI",
        "subtitle": "Google Pay, PhonePe, Paytm",
        "icon": "Smartphone",
        "isRecommended": True,
        "requiresInstrument": True,
        "instrumentLabel": "UPI ID (e.g. name@bank)",
    },
    {
        "id": "CARD",
        "title": "Credit / Debit Card",
        "subtitle": "Visa, Mastercard, RuPay - 3D Secure",
        "icon": "CreditCard",
        "isRecommended": False,
        "requiresInstrument": True,
        "instrumentLabel": "Card number",
    },
    {
        "id": "WALLET",
        "title": "Zepto Wallet",
        "subtitle": "Pay from your promo balance",
        "icon": "Wallet",
        "isRecommended": False,
        "requiresInstrument": False,
        "instrumentLabel": None,
    },
    {
        "id": "COD",
        "title": "Cash on Delivery",
        "subtitle": "Pay cash or UPI at your doorstep",
        "icon": "Banknote",
        "isRecommended": False,
        "requiresInstrument": False,
        "instrumentLabel": None,
    },
]


def _mask_instrument(method: str, instrument: Optional[str]) -> Optional[str]:
    """Keeps only a non-reversible hint: the UPI handle, or card last-4."""
    if not instrument:
        return None
    raw = instrument.strip()
    if method == "UPI":
        return raw if "@" in raw else None
    if method == "CARD":
        digits = "".join(ch for ch in raw if ch.isdigit())
        return f"**** **** **** {digits[-4:]}" if len(digits) >= 4 else None
    return None


def list_methods(amount_paise: int) -> Dict[str, Any]:
    """Payment options for an amount, in quickpay listing shape."""
    amount_rupees = to_rupees(amount_paise)
    methods: List[Dict[str, Any]] = []

    for entry in METHOD_CATALOGUE:
        method = dict(entry)
        method["amount"] = amount_paise
        method["formattedAmount"] = format_rupees(amount_paise)
        method["isEnabled"] = True

        if method["id"] == "WALLET":
            method["walletBalance"] = to_paise(WALLET_BALANCE_RUPEES)
            method["isEnabled"] = amount_rupees <= WALLET_BALANCE_RUPEES
            method["subtitle"] = (
                f"Balance {format_rupees(to_paise(WALLET_BALANCE_RUPEES))}"
                if method["isEnabled"]
                else f"Insufficient balance ({format_rupees(to_paise(WALLET_BALANCE_RUPEES))})"
            )

        methods.append(method)

    return {
        "errors": [],
        "data": {
            "amount": amount_paise,
            "formattedAmount": format_rupees(amount_paise),
            "paymentMethods": methods,
            "installedUpiApps": [],
            "isCredPayEligible": False,
            "ptpActionType": "PAY_NOW",
        },
    }


def initiate(
    db: Session,
    account_id: str,
    amount_paise: int,
    payment_method: str,
    instrument: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a payment transaction and returns the gateway handoff details."""
    method = (payment_method or "").strip().upper()
    if method not in PAYMENT_METHODS:
        return {"success": False, "error": f"Unsupported payment method '{payment_method}'"}

    amount_rupees = to_rupees(amount_paise)
    if amount_rupees <= 0:
        return {"success": False, "error": "Payment amount must be greater than zero"}

    if method == "WALLET" and amount_rupees > WALLET_BALANCE_RUPEES:
        return {
            "success": False,
            "error": (
                f"Wallet balance {format_rupees(to_paise(WALLET_BALANCE_RUPEES))} "
                "is not enough for this order"
            ),
        }

    if method in ("UPI", "CARD") and not instrument:
        return {"success": False, "error": "Enter your UPI ID or card number to continue"}

    if method == "UPI" and instrument and "@" not in instrument:
        return {"success": False, "error": "Enter a valid UPI ID, for example name@bank"}

    if method == "CARD":
        digits = "".join(ch for ch in (instrument or "") if ch.isdigit())
        if len(digits) < 12:
            return {"success": False, "error": "Enter a valid card number"}

    reference = f"{REFERENCE_PREFIX}_{secrets.token_hex(8)}"
    status = "AUTHORIZED" if method in PREPAID_METHODS else "SUCCESS"

    transaction = PaymentTransaction(
        id=str(uuid.uuid4()),
        account_id=account_id,
        reference=reference,
        amount=amount_rupees,
        payment_method=method,
        status=status,
        instrument_hint=_mask_instrument(method, instrument),
        completed_at=None if method in PREPAID_METHODS else datetime.utcnow(),
    )
    db.add(transaction)
    db.commit()

    return {
        "success": True,
        "reference": reference,
        "amount": amount_paise,
        "formattedAmount": format_rupees(amount_paise),
        "paymentMethod": method,
        "status": status,
        "instrumentHint": transaction.instrument_hint,
        "requiresConfirmation": method in PREPAID_METHODS,
        "expiresInMinutes": TRANSACTION_TTL_MINUTES,
    }


def get(db: Session, reference: str) -> Optional[PaymentTransaction]:
    """Looks up a transaction by its gateway reference."""
    return (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.reference == reference)
        .first()
    )


def confirm(
    db: Session,
    reference: str,
    account_id: str,
    succeeded: bool = True,
    failure_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Applies the gateway outcome to a pending transaction."""
    transaction = get(db, reference)
    if not transaction:
        return {"success": False, "error": "Payment reference not found"}
    if transaction.account_id != account_id:
        return {"success": False, "error": "Payment reference does not belong to this account"}

    if transaction.status in ("SUCCESS", "FAILED", "EXPIRED"):
        return {
            "success": True,
            "reference": transaction.reference,
            "status": transaction.status,
            "alreadyFinal": True,
        }

    transaction.status = "SUCCESS" if succeeded else "FAILED"
    transaction.failure_reason = None if succeeded else (failure_reason or "Payment declined")
    transaction.completed_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "reference": transaction.reference,
        "status": transaction.status,
        "failureReason": transaction.failure_reason,
        "formattedAmount": format_rupees(to_paise(transaction.amount)),
        "paymentMethod": transaction.payment_method,
    }


def serialize(transaction: PaymentTransaction) -> Dict[str, Any]:
    """Public view of a transaction."""
    return {
        "reference": transaction.reference,
        "amount": to_paise(transaction.amount),
        "formattedAmount": format_rupees(to_paise(transaction.amount)),
        "paymentMethod": transaction.payment_method,
        "status": transaction.status,
        "instrumentHint": transaction.instrument_hint,
        "failureReason": transaction.failure_reason,
        "orderId": transaction.order_id,
        "createdAt": (
            transaction.created_at.isoformat() + "Z" if transaction.created_at else None
        ),
    }


def verify_paid(
    db: Session, reference: Optional[str], account_id: str, amount_rupees: float
) -> Dict[str, Any]:
    """Confirms a reference is a settled, unused payment for exactly this amount."""
    if not reference:
        return {"ok": False, "error": "A completed payment is required before placing the order"}

    transaction = get(db, reference)
    if not transaction:
        return {"ok": False, "error": "Payment reference not found"}
    if transaction.account_id != account_id:
        return {"ok": False, "error": "Payment reference does not belong to this account"}
    if transaction.status != "SUCCESS":
        return {"ok": False, "error": f"Payment is {transaction.status.lower()}, not completed"}
    if to_paise(amount_rupees) != to_paise(transaction.amount):
        return {
            "ok": False,
            "error": "Payment amount does not match the order total. Refresh and try again.",
        }
    if transaction.order_id:
        return {"ok": False, "error": "This payment has already been used for another order"}

    return {"ok": True, "transaction": transaction}
