"""Payment router.

Documented endpoint
    POST /payment-service/payment-listing-api/v1/quickpay

Supporting endpoints
    POST /payment-service/api/v1/payments/initiate
    POST /payment-service/api/v1/payments/{reference}/confirm
    GET  /payment-service/api/v1/payments/{reference}

All amounts on the wire are paise.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.zepto import payment_gateway
from backend.zepto.deps import AuthContext, require_auth

router = APIRouter(tags=["Payments"])


class QuickPayRequest(BaseModel):
    """Body of POST /payment-service/payment-listing-api/v1/quickpay."""

    installedUpiApps: list[str] = Field(default_factory=list)
    sourceId: Optional[str] = None
    source: str = "CHECKOUT"
    isCredPayEligible: bool = False
    sourceToken: Optional[str] = None
    ptpActionType: str = "PAY_NOW"
    amount: int = 0


class InitiatePaymentRequest(BaseModel):
    """Body of the payment initiate endpoint. `amount` is in paise."""

    amount: int = Field(..., gt=0)
    paymentMethod: str = Field(..., examples=["UPI"])
    instrument: Optional[str] = Field(
        default=None, description="UPI ID or card number. Never stored in full."
    )


class ConfirmPaymentRequest(BaseModel):
    """Body of the payment confirm endpoint (gateway callback shape)."""

    succeeded: bool = True
    failureReason: Optional[str] = None


@router.post("/payment-service/payment-listing-api/v1/quickpay")
def quickpay(req: QuickPayRequest) -> Dict[str, Any]:
    """Lists the payment instruments available for the requested amount."""
    result = payment_gateway.list_methods(req.amount)
    result["paymentMethods"] = result.get("data", {}).get("paymentMethods", [])
    return result


@router.post("/payment-service/api/v1/payments/initiate")
def initiate_payment(
    req: InitiatePaymentRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Opens a payment transaction for the cart total."""
    result = payment_gateway.initiate(
        db=db,
        account_id=ctx.account_id,
        amount_paise=req.amount,
        payment_method=req.paymentMethod,
        instrument=req.instrument,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/payment-service/api/v1/payments/{reference}/confirm")
def confirm_payment(
    reference: str,
    req: ConfirmPaymentRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Settles a pending payment as successful or failed."""
    result = payment_gateway.confirm(
        db=db,
        reference=reference,
        account_id=ctx.account_id,
        succeeded=req.succeeded,
        failure_reason=req.failureReason,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/payment-service/api/v1/payments/{reference}")
def get_payment(
    reference: str,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the current status of a payment reference."""
    transaction = payment_gateway.get(db, reference)
    if not transaction or transaction.account_id != ctx.account_id:
        raise HTTPException(status_code=404, detail="Payment reference not found")
    return payment_gateway.serialize(transaction)
