"""Account and User Profile router.

Documented endpoints
    POST /api/v2/user/customer/info/
    GET  /api/v1/wallet-balances/total
    GET  /api/v1/pass/overview
    GET  /api/v1/user/customer/referrals/

Supporting endpoints
    GET  /api/v2/user/customer/info/
    GET  /api/v1/user/customer/addresses/
    POST /api/v1/user/customer/addresses/
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.addresses import AddressService
from backend.api.users import UserService
from backend.database.connection import get_db
from backend.database.crypto import decrypt_data, mask_phone_number
from backend.database.models import ShoppingAccount
from backend.zepto.deps import AuthContext, optional_auth, require_auth

router = APIRouter(tags=["Account"])


class CustomerInfoRequest(BaseModel):
    """Body of POST /api/v2/user/customer/info/."""

    appVersion: Optional[str] = "2.0.0"
    bundleVersion: Optional[str] = "2.0.0"
    deviceUid: Optional[str] = None
    platform: Optional[str] = "WEB"


class AddressCreateRequest(BaseModel):
    """Body of address creation."""

    formattedAddress: str = Field(..., examples=["Flat 402, Sunshine Heights, Mumbai"])
    landmark: Optional[str] = None
    houseNumber: Optional[str] = None
    city: str = "Mumbai"
    pincode: str = "400001"
    addressType: str = "HOME"
    latitude: float = 19.0760
    longitude: float = 72.8777
    isDefault: bool = False


def _build_customer_info(account: Optional[ShoppingAccount]) -> Dict[str, Any]:
    """Builds customer info payload matching the observed Zepto schema."""
    if account:
        raw_phone = decrypt_data(account.encrypted_mobile) or "9876542168"
        account_id = account.id
        full_name = account.display_name or "Valued Customer"
    else:
        raw_phone = "9876542168"
        account_id = "guest_account"
        full_name = "Guest User"

    return {
        "user": {
            "id": account_id,
            "fullName": full_name,
            "mobileNumber": mask_phone_number(raw_phone),
            "countryCode": "+91",
            "emailId": None,
            "isRegistered": True,
            "isUserFullNameSet": True,
            "lastOrderNotified": False,
            "isInternalUser": False,
            "isInternationalUser": False,
            "isBetaUser": None,
            "blockRefererral": False,
        },
        "ongoingOrderId": None,
        "ongoingOrderCreationTime": None,
        "userAggregate": {
            "AVERAGE_ARRIVAL_TIME": 12,
            "AVERAGE_ORDER_VALUE": 380,
            "CDP_ASV_MEDIAN": 320,
            "CDP_COUNTRY_CODE": "+91",
            "CDP_DEVICE_PRICE_RANGE": "MID",
            "CDP_GPPO_MEDIAN": 45,
            "CDP_L28_DAYS_ACTIVE_GPPO_NTILE": 1,
            "CDP_L28_DAYS_MAX_RECENCY": 2,
            "CDP_L3M_GPPO_MEDIAN": 50,
            "CDP_LAST_12_WEEKS_ACTIVE": 4,
            "CDP_LAST_3_MONTHS_WEEKLY_FREQ_MEDIAN": 2,
            "CDP_LAST_ORDER_MONTH_USER_GPPO_DECILE": 3,
        },
        "referralExperiment": {
            "active": True,
            "referral_revamp_enabled": True,
            "sub_variant": "CONTROL",
            "variant": "V1",
        },
        "userTncPrivacyInfo": {
            "isTncPrivacyPolicyAccepted": True,
            "isTncPrivacyPolicyMandatory": False,
        },
        "noBagDeliveryUserType": "STANDARD",
        "isNewFont": True,
        "disableCgOnScreen": [],
    }


@router.post("/api/v2/user/customer/info/")
def customer_info_post(
    req: Optional[CustomerInfoRequest] = None,
    ctx: Optional[AuthContext] = Depends(optional_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the customer profile and aggregate behavioral data."""
    account = ctx.account if ctx else None
    if not account:
        account = db.query(ShoppingAccount).first()
    return _build_customer_info(account)


@router.get("/api/v2/user/customer/info/")
def customer_info_get(
    ctx: Optional[AuthContext] = Depends(optional_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """GET variant of customer info for web client fallbacks."""
    account = ctx.account if ctx else None
    if not account:
        account = db.query(ShoppingAccount).first()
    return _build_customer_info(account)


@router.get("/api/v1/wallet-balances/total")
def wallet_balances(
    includePendingGiftCardInfo: bool = Query(False),
    ctx: Optional[AuthContext] = Depends(optional_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns wallet, promotional, and gift card balances."""
    account_id = ctx.account.id if ctx else None
    if account_id:
        return UserService.get_wallet_balances(db, account_id)
    return {
        "totalBalance": 50.0,
        "availableBalance": 50.0,
        "totalPromotionalBalance": 25.0,
        "available": True,
        "hasPendingGiftCard": False,
        "totalBalanceNumericalAbbreviation": "₹50",
    }


@router.get("/api/v1/pass/overview")
def pass_overview(
    ctx: Optional[AuthContext] = Depends(optional_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the Zepto Pass loyalty status and lifetime savings."""
    account_id = ctx.account.id if ctx else None
    if account_id:
        return UserService.get_pass_overview(db, account_id)
    return {
        "showBadge": True,
        "showBottomsheet": False,
        "variantName": "standard",
        "productOffers": [],
        "passLockedStateText": "Free delivery above ₹99",
        "suggestedPass": None,
        "membership": None,
        "userCohort": "DEFAULT",
        "lifetimeSavings": {
            "totalPurchaseFee": 0,
            "totalSavingsAmount": 450.0,
            "totalPreviousSavingsAmount": 0,
            "isMember": True,
            "totalDailyPurchaseFee": 0,
            "totalDailySavingsAmount": 0,
            "totalRoyalePurchaseFee": 0,
            "totalRoyaleSavingsAmount": 0,
            "totalRoyaleOrderCount": 0,
            "savingsBreakdown": [],
            "totalOrders": 12,
        },
        "brandsInfo": [],
        "renewalDurationTitle": [],
        "renewalPreExpiryInfo": [],
    }


@router.get("/api/v1/user/customer/referrals/")
def referrals(
    ctx: Optional[AuthContext] = Depends(optional_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns referral program details, links, and rewards."""
    account_id = ctx.account.id if ctx else None
    if account_id:
        return UserService.get_referral_summary(db, account_id)
    return {
        "uiSchema": {
            "benefitsWidget": {
                "advocate": "Earn ₹100 for each friend who places an order",
                "receiver": "Get ₹100 off on your first order",
            },
            "header": {
                "image": "https://cdn.zeptonow.com/referral-banner.png",
                "subtitle": "Invite friends & family to Zepto",
                "title": "Refer & Earn",
            },
            "stepsToRefer": {
                "footer": "Terms & Conditions apply",
                "steps": ["Share referral link", "Friend places first order", "You get ₹100"],
                "title": "How it works",
            },
        },
        "pageLayout": None,
        "referralCode": "ZEPTO100",
    }


@router.get("/api/v1/user/customer/addresses/")
def get_customer_addresses(
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Returns saved delivery addresses for the active account."""
    return {"addresses": AddressService.get_addresses(db, ctx.account_id)}


@router.post("/api/v1/user/customer/addresses/")
def add_customer_address(
    req: AddressCreateRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Adds a delivery address for the active account."""
    address_data = req.model_dump()
    addresses = AddressService.add_address(db, ctx.account_id, address_data)
    return {"success": True, "addresses": addresses}
