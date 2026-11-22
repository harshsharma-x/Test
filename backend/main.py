"""Centralized FastAPI Backend for Zepto Shopping Ecosystem.
Connects web application, API integration engine, database, and Telegram bot.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.accounts.manager import MultiAccountManager
from backend.api.addresses import AddressService
from backend.api.authentication import AuthenticationService
from backend.api.cart import CartService
from backend.api.checkout import CheckoutService
from backend.api.delivery import DeliveryService
from backend.api.inventory import InventoryService
from backend.api.offers import OfferService
from backend.api.orders import OrderService
from backend.api.payments import PaymentService
from backend.api.products import ProductService
from backend.api.search import SearchService
from backend.api.support import SupportService
from backend.api.users import UserService
from backend.database.connection import get_db, init_db
from backend.database.models import ApiLog, ShoppingAccount, User
from backend.offers.engine import BestOfferEngine
from backend.services.export_import import AccountBackupService
from backend.zepto.routers import all_routers

from backend.zepto.routers import all_routers as _zepto_all_routers

app = FastAPI(
    title="Zepto Shopping Platform API",
    version="2.0.0",
    description="Centralized multi-account shopping platform with best-offer engine & Telegram bot integration.",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bind the real Zepto-compatible API surface (LMS/CFS/search/cart/orders/...).
for _router in _zepto_all_routers():
    app.include_router(_router)


@app.on_event("startup")
def on_startup():
    init_db()


# Middleware for API logging
@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000

    # Log API calls to db if not static
    if request.url.path.startswith("/api/"):
        try:
            from backend.database.connection import SessionLocal
            with SessionLocal() as db:
                log = ApiLog(
                    endpoint_name=request.url.path,
                    method=request.method,
                    status_code=response.status_code,
                    execution_time=duration_ms,
                )
                db.add(log)
                db.commit()
        except Exception:
            pass

    return response


# --- Auth Dependency Helper ---
def get_current_user_and_account(
    db: Session = Depends(get_db),
    x_account_id: Optional[str] = Header(None, alias="X-Account-Id"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> tuple[User, ShoppingAccount]:
    """Resolves master user and active shopping account from headers or defaults."""
    # Find master user
    if x_user_id:
        user = db.query(User).filter(User.id == x_user_id).first()
    else:
        user = db.query(User).first()

    if not user:
        user = User(id="user_master_default", telegram_id="default_user")
        db.add(user)
        db.commit()
        db.refresh(user)

    # Find account
    account = None
    if x_account_id:
        account = db.query(ShoppingAccount).filter(ShoppingAccount.id == x_account_id, ShoppingAccount.user_id == user.id).first()

    if not account:
        account = (
            db.query(ShoppingAccount)
            .filter(ShoppingAccount.user_id == user.id)
            .order_by(ShoppingAccount.last_used_at.desc(), ShoppingAccount.is_default.desc())
            .first()
        )

    if not account:
        from backend.database.crypto import encrypt_data
        account = ShoppingAccount(
            user_id=user.id,
            encrypted_mobile=encrypt_data("9876542168") or "",
            display_name="Personal Account",
            status="ACTIVE",
            is_default=True,
        )
        db.add(account)
        db.commit()
        db.refresh(account)

    return user, account


# --- Schemas ---
class SendOtpRequest(BaseModel):
    mobile_number: Optional[str] = Field(default=None, example="9876542168")
    mobileNumber: Optional[str] = None
    country_code: str = "+91"
    countryCode: str = "+91"


class VerifyOtpRequest(BaseModel):
    mobile_number: Optional[str] = None
    mobileNumber: Optional[str] = None
    otp_token: Optional[str] = None
    otpToken: Optional[str] = None
    display_name: Optional[str] = None
    fullName: Optional[str] = None
    country_code: str = "+91"
    countryCode: str = "+91"
    challengeId: Optional[str] = None
    challenge_id: Optional[str] = None


class SwitchAccountRequest(BaseModel):
    account_id: Optional[str] = None
    accountId: Optional[str] = None


class AddAccountRequest(BaseModel):
    mobile_number: str
    display_name: str


class RenameAccountRequest(BaseModel):
    display_name: str


class CartItemRequest(BaseModel):
    product_id: str
    quantity: int = 1


class ValidateCouponRequest(BaseModel):
    code: str


class CheckoutOrderRequest(BaseModel):
    payment_method: str = "UPI"
    address_id: Optional[str] = None
    coupon_code: Optional[str] = None


class RateOrderRequest(BaseModel):
    order_id: str
    rating: int
    feedback: str = ""


# --- 1. Authentication Endpoints ---
@app.get("/api/auth/csrf")
def get_csrf_token():
    return AuthenticationService.create_csrf_token()


@app.post("/api/auth/send-otp")
def send_otp(req: SendOtpRequest):
    mobile = req.mobile_number or req.mobileNumber or ""
    code = req.country_code or req.countryCode or "+91"
    return AuthenticationService.send_otp(mobile, code)


@app.post("/api/auth/verify-otp")
def verify_otp(
    req: VerifyOtpRequest,
    response: Response,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    user, _ = user_account
    mobile = req.mobile_number or req.mobileNumber or ""
    otp = req.otp_token or req.otpToken or ""
    name = req.display_name or req.fullName
    code = req.country_code or req.countryCode or "+91"
    challenge = req.challengeId or req.challenge_id
    res = AuthenticationService.verify_otp(
        db=db,
        mobile_number=mobile,
        otp_token=otp,
        display_name=name,
        user_id=user.id,
        country_code=code,
        challenge_id=challenge,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Verification failed"))

    if "session_token" in res:
        response.set_cookie(
            key="zepto_session",
            value=res["session_token"],
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="lax",
            path="/",
        )
        res["sessionToken"] = res["session_token"]
        res["accountId"] = res.get("account_id")
    return res


# --- 2. Accounts Endpoints ---
@app.get("/api/accounts")
def list_accounts(
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    user, active = user_account
    accounts = MultiAccountManager.list_accounts(db, user.id)
    return {
        "activeAccountId": active.id,
        "accounts": accounts,
    }


@app.post("/api/accounts/switch")
def switch_account(
    req: SwitchAccountRequest,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    user, _ = user_account
    res = MultiAccountManager.switch_account(db, user.id, req.account_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.post("/api/accounts/add")
def add_account(
    req: AddAccountRequest,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    user, _ = user_account
    res = MultiAccountManager.add_account(db, user.id, req.mobile_number, req.display_name)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.put("/api/accounts/{account_id}/rename")
def rename_account(
    account_id: str,
    req: RenameAccountRequest,
    db: Session = Depends(get_db),
):
    res = MultiAccountManager.rename_account(db, account_id, req.display_name)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.post("/api/accounts/{account_id}/default")
def set_default_account(
    account_id: str,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    user, _ = user_account
    res = MultiAccountManager.set_default_account(db, user.id, account_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.delete("/api/accounts/{account_id}")
def remove_account(
    account_id: str,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    user, _ = user_account
    res = MultiAccountManager.remove_account(db, user.id, account_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.get("/api/user/profile")
def get_user_profile(
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    info = UserService.get_customer_info(db, account.id)
    pass_info = UserService.get_pass_overview(db, account.id)
    wallet = UserService.get_wallet_balances(db, account.id)
    referral = UserService.get_referral_summary(db, account.id)
    return {
        "profile": info,
        "pass": pass_info,
        "wallet": wallet,
        "referral": referral,
    }


# --- 3. Catalogue & Products Endpoints ---
@app.get("/api/products/page")
def get_catalogue_page(
    page_type: str = "HOME",
    page_size: int = 30,
    db: Session = Depends(get_db),
):
    return ProductService.get_page(db, page_type=page_type, page_size=page_size)


@app.get("/api/products/buy-again")
def get_buy_again(
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return ProductService.get_buy_again(db, account.id)


@app.get("/api/products/{product_id}")
def get_product_detail(product_id: str, db: Session = Depends(get_db)):
    p = ProductService.get_product_detail(db, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return p


# --- 4. Search Endpoints ---
@app.get("/api/search")
def search_products(
    q: str = "",
    category: Optional[str] = None,
    sort_by: Optional[str] = None,
    page: int = 0,
    db: Session = Depends(get_db),
):
    return SearchService.search_products(db, query=q, category=category, sort_by=sort_by, page=page)


@app.get("/api/search/suggestions")
def get_search_suggestions(q: str = "", db: Session = Depends(get_db)):
    return {"suggestions": SearchService.get_suggestions(db, q)}


# --- 5. Cart Endpoints (Account Isolated) ---
@app.get("/api/cart")
def get_cart(
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return CartService.get_cart_details(db, account.id)


@app.post("/api/cart/items")
def add_to_cart(
    req: CartItemRequest,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return CartService.add_to_cart(db, account.id, req.product_id, req.quantity)


@app.put("/api/cart/items/{product_id}")
def update_cart_quantity(
    product_id: str,
    req: CartItemRequest,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return CartService.update_quantity(db, account.id, product_id, req.quantity)


@app.delete("/api/cart/items/{product_id}")
def remove_from_cart(
    product_id: str,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return CartService.remove_from_cart(db, account.id, product_id)


@app.delete("/api/cart")
def clear_cart(
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return CartService.clear_cart(db, account.id)


# --- 6. Offers & Best-Offer Engine ---
@app.get("/api/offers")
def list_offers_for_cart(
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    cart_info = CartService.get_cart_details(db, account.id)
    return {
        "evaluation": BestOfferEngine.evaluate_best_offer(db, account.id),
        "availableOffers": OfferService.get_available_offers_for_cart(db, cart_info["cartTotal"], account.id),
    }


@app.post("/api/offers/validate")
def validate_coupon(
    req: ValidateCouponRequest,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    cart_info = CartService.get_cart_details(db, account.id)
    res = OfferService.validate_and_apply_coupon(db, req.code, cart_info["cartTotal"])
    if not res.get("valid"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.post("/api/offers/auto-apply-best")
def auto_apply_best_offer(
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    """Executes the Intelligent Automatic Best-Offer Engine."""
    _, account = user_account
    res = BestOfferEngine.auto_apply_best_offer(db, account.id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


# --- 7. Addresses & Location ---
@app.get("/api/addresses")
def get_addresses(
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return {"addresses": AddressService.get_addresses(db, account.id)}


@app.post("/api/addresses")
def add_address(
    address: Dict[str, Any],
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return {"addresses": AddressService.add_address(db, account.id, address)}


@app.get("/api/location/serviceability")
def check_serviceability(lat: float = 19.0760, lng: float = 72.8777):
    return InventoryService.check_serviceability(lat, lng)


# --- 8. Checkout & Payments ---
@app.get("/api/checkout/summary")
def get_checkout_summary(
    coupon_code: Optional[str] = None,
    address_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return CheckoutService.get_checkout_summary(db, account.id, coupon_code, address_id)


@app.get("/api/payments/methods")
def get_payment_methods(amount: float = 0.0):
    return {"methods": PaymentService.get_payment_methods(amount)}


@app.post("/api/payments/initiate")
def initiate_payment(
    payment_method: str = "UPI",
    amount: float = 0.0,
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return PaymentService.initiate_payment_handoff(account.id, amount, payment_method)


# --- 9. Orders & Delivery ---
@app.post("/api/orders")
def place_order(
    req: CheckoutOrderRequest,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    res = OrderService.create_order(
        db,
        account_id=account.id,
        payment_method=req.payment_method,
        address_id=req.address_id,
        coupon_code=req.coupon_code,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.get("/api/orders")
def list_orders(
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    _, account = user_account
    return {"orders": OrderService.list_orders(db, account.id)}


@app.get("/api/orders/{order_id}")
def get_order_details(order_id: str, db: Session = Depends(get_db)):
    det = OrderService.get_order_details(db, order_id)
    if not det:
        raise HTTPException(status_code=404, detail="Order not found")
    return det


@app.post("/api/orders/{order_id}/cancel")
def cancel_order(order_id: str, db: Session = Depends(get_db)):
    res = OrderService.cancel_order(db, order_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.get("/api/delivery/track/{order_id}")
def track_order(order_id: str):
    return DeliveryService.get_live_tracking(order_id)


# --- 10. Data Backup / Import & Export ---
@app.get("/api/backup/export")
def export_accounts(
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    user, _ = user_account
    return AccountBackupService.export_accounts(db, user.id)


@app.post("/api/backup/preview")
def preview_import(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    user, _ = user_account
    res = AccountBackupService.preview_import(db, user.id, payload)
    if not res.get("valid"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@app.post("/api/backup/import")
def confirm_import(
    payload: Dict[str, Any],
    overwrite: bool = False,
    db: Session = Depends(get_db),
    user_account=Depends(get_current_user_and_account),
):
    user, _ = user_account
    res = AccountBackupService.confirm_import(db, user.id, payload, overwrite_duplicates=overwrite)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


# --- 11. Support Endpoints ---
@app.get("/api/support/faqs")
def get_faqs():
    return {"faqs": SupportService.get_faq_topics()}


@app.post("/api/support/rate")
def rate_order(req: RateOrderRequest):
    return SupportService.submit_rating(req.order_id, req.rating, req.feedback)


# --- Health & Status ---
@app.get("/healthz")
def healthz():
    return {"status": "ok", "timestamp": time.time()}


# --- Mount Zepto Native API Routers ---
for zepto_router in all_routers():
    app.include_router(zepto_router)


# Static Frontend mount
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "public"
if FRONTEND_DIST.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIST)), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index_file = FRONTEND_DIST / "index.html"
        requested = FRONTEND_DIST / full_path
        if requested.exists() and requested.is_file():
            return FileResponse(requested)
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"message": "Zepto Shopping Platform Backend Active", "docs": "/docs"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
