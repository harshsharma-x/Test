"""Users API: Customer profile, wallet balances, pass overview, referrals."""
from __future__ import annotations

from typing import Any, Dict
from sqlalchemy.orm import Session

from backend.database.crypto import decrypt_data, mask_phone_number
from backend.database.models import ShoppingAccount


class UserService:
    @staticmethod
    def get_customer_info(db: Session, account_id: str) -> Dict[str, Any]:
        """Customer info matching POST /api/v2/user/customer/info/."""
        account = db.query(ShoppingAccount).filter(ShoppingAccount.id == account_id).first()
        if not account:
            return {"error": "Account not found"}

        raw_phone = decrypt_data(account.encrypted_mobile) or "9876543210"
        return {
            "user": {
                "id": account.id,
                "fullName": account.display_name,
                "mobileNumber": mask_phone_number(raw_phone),
                "countryCode": "+91",
                "emailId": None,
                "isRegistered": True,
                "isUserFullNameSet": True,
                "lastOrderNotified": True,
                "referralCode": "ZEPTO" + raw_phone[-4:],
                "userType": "CUSTOMER",
                "whatsappOpted": "PENDING",
            },
            "ongoingOrderId": None,
            "userAggregate": {
                "AVERAGE_ARRIVAL_TIME": 10,
                "AVERAGE_ORDER_VALUE": 320.0,
                "DAYS_SINCE_REGISTRATION": 45,
                "CURRENT_PASS_MOV": 0,
            },
        }

    @staticmethod
    def get_wallet_balances(db: Session, account_id: str) -> Dict[str, Any]:
        """Wallet balances matching GET /api/v1/wallet-balances/total."""
        return {
            "totalBalance": 50.0,
            "availableBalance": 50.0,
            "totalPromotionalBalance": 25.0,
            "available": True,
            "hasPendingGiftCard": False,
            "totalBalanceNumericalAbbreviation": "₹50",
        }

    @staticmethod
    def get_pass_overview(db: Session, account_id: str) -> Dict[str, Any]:
        """Zepto Pass overview matching GET /api/v1/pass/overview."""
        return {
            "showBadge": True,
            "showBottomsheet": False,
            "variantName": "ZEPTO_PASS_V1",
            "passLockedStateText": "Free delivery above ₹99",
            "userCohort": "LOYALTY_T2",
            "lifetimeSavings": {
                "totalSavingsAmount": 450.0,
                "totalOrders": 12,
                "isMember": True,
            },
        }

    @staticmethod
    def get_referral_summary(db: Session, account_id: str) -> Dict[str, Any]:
        """Referral schema matching GET /api/v1/user/customer/referrals/."""
        account = db.query(ShoppingAccount).filter(ShoppingAccount.id == account_id).first()
        raw_phone = decrypt_data(account.encrypted_mobile) if account else "0000"
        ref_code = "ZEPTO" + (raw_phone[-4:] if raw_phone else "REF")
        return {
            "referralCode": ref_code,
            "uiSchema": {
                "benefitsWidget": {
                    "advocate": {"text": "25% off up to ₹200 on next order"},
                    "receiver": {"text": "25% off up to ₹50 on first order"},
                }
            },
        }
