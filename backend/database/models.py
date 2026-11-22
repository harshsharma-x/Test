"""SQLAlchemy models for multi-account shopping platform."""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship, synonym

Base = declarative_base()


class User(Base):
    """Platform master user, which may be linked to Telegram or Web."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_id = Column(String(64), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    accounts = relationship("ShoppingAccount", back_populates="user", cascade="all, delete-orphan")


class ShoppingAccount(Base):
    """Specific linked shopping phone account (e.g. personal, secondary)."""
    __tablename__ = "shopping_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    encrypted_mobile = Column(Text, nullable=False)
    display_name = Column(String(128), nullable=False, default="Shopping Account")
    status = Column(String(32), default="ACTIVE")  # ACTIVE, REAUTHENTICATION_REQUIRED, EXPIRED
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="accounts")
    sessions = relationship("AccountSession", back_populates="account", cascade="all, delete-orphan")
    cart = relationship("ShoppingCart", back_populates="account", uselist=False, cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="account", cascade="all, delete-orphan")
    preferences = relationship("AccountPreference", back_populates="account", uselist=False, cascade="all, delete-orphan")


class AccountSession(Base):
    """Authorized auth session tokens per account."""
    __tablename__ = "account_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String(36), ForeignKey("shopping_accounts.id"), nullable=False, index=True)
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    session_data_json = Column(Text, nullable=True)  # cookies or storage state
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("ShoppingAccount", back_populates="sessions")


class Product(Base):
    """Product catalog item."""
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_product_id = Column(String(64), unique=True, index=True, nullable=True)
    name = Column(String(256), nullable=False, index=True)
    brand = Column(String(128), nullable=True, index=True)
    category = Column(String(128), nullable=False, default="Groceries", index=True)
    price = Column(Float, nullable=False)  # in Rupees
    original_price = Column(Float, nullable=False)
    discount_percent = Column(Integer, default=0)
    unit = Column(String(64), default="1 pc")
    image_url = Column(Text, nullable=True)
    availability = Column(Boolean, default=True)
    stock_quantity = Column(Integer, default=100)

    # Alias expected by the real Zepto API / integration tests.
    in_stock = synonym("availability")
    rating = Column(Float, default=4.5)
    description = Column(Text, nullable=True)


class ShoppingCart(Base):
    """Isolated shopping cart per account."""
    __tablename__ = "shopping_carts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String(36), ForeignKey("shopping_accounts.id"), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship("ShoppingAccount", back_populates="cart")
    items = relationship("ShoppingCartItem", back_populates="cart", cascade="all, delete-orphan")


class ShoppingCartItem(Base):
    """Items inside a cart."""
    __tablename__ = "shopping_cart_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cart_id = Column(String(36), ForeignKey("shopping_carts.id"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)

    cart = relationship("ShoppingCart", back_populates="items")
    product = relationship("Product")


class Offer(Base):
    """Promotions, bank discounts, and coupons."""
    __tablename__ = "offers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_offer_id = Column(String(64), unique=True, index=True, nullable=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    offer_type = Column(String(32), default="PERCENTAGE")  # PERCENTAGE, FLAT, FREE_DELIVERY
    discount_value = Column(Float, nullable=False)
    min_cart_value = Column(Float, default=0.0)
    max_discount = Column(Float, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    # Aliases expected by the real Zepto API / integration tests.
    discount_type = synonym("offer_type")
    min_order_amount = synonym("min_cart_value")
    max_discount_amount = synonym("max_discount")


class OfferHistory(Base):
    """Historical audit of applied offers."""
    __tablename__ = "offer_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String(36), ForeignKey("shopping_accounts.id"), nullable=False, index=True)
    offer_id = Column(String(36), ForeignKey("offers.id"), nullable=False)
    discount_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    """Order history per account."""
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String(36), ForeignKey("shopping_accounts.id"), nullable=False, index=True)
    external_order_id = Column(String(64), index=True, nullable=True)
    status = Column(String(32), default="PLACED")  # PLACED, PACKING, OUT_FOR_DELIVERY, DELIVERED, CANCELLED
    total_amount = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0.0)
    delivery_fee = Column(Float, default=0.0)
    items_json = Column(Text, nullable=False)  # JSON snapshot of products purchased
    delivery_address = Column(Text, nullable=True)
    eta_minutes = Column(Integer, default=10)
    payment_method = Column(String(32), default="UPI")
    payment_status = Column(String(32), default="PENDING")  # PENDING, PAID, COD_DUE, REFUNDED
    transaction_reference = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("ShoppingAccount", back_populates="orders")


class AccountPreference(Base):
    """Account preferences and settings."""
    __tablename__ = "account_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String(36), ForeignKey("shopping_accounts.id"), unique=True, nullable=False)
    preferences_json = Column(Text, default="{}")

    account = relationship("ShoppingAccount", back_populates="preferences")


class ApiLog(Base):
    """Audit log for API calls."""
    __tablename__ = "api_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    endpoint_name = Column(String(256), nullable=False)
    method = Column(String(16), nullable=False)
    status_code = Column(Integer, nullable=False)
    execution_time = Column(Float, nullable=False)  # in milliseconds
    created_at = Column(DateTime, default=datetime.utcnow)


class OtpChallenge(Base):
    """A one-time password challenge issued for a mobile number.

    Only a salted hash of the code is persisted; the plain code never touches
    the database so a leaked DB cannot be replayed against the login flow.
    """
    __tablename__ = "otp_challenges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mobile_digits = Column(String(16), nullable=False, index=True)
    code_hash = Column(String(128), nullable=False)
    purpose = Column(String(32), default="LOGIN")  # LOGIN, LINK_ACCOUNT
    attempts = Column(Integer, default=0, nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class AuthSession(Base):
    """Bearer-token session issued after a successful OTP verification."""
    __tablename__ = "auth_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    active_account_id = Column(String(36), ForeignKey("shopping_accounts.id"), nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class PaymentTransaction(Base):
    """Payment attempt record. Card/UPI credentials are never stored - only the
    gateway reference, the amount, and the resulting status."""
    __tablename__ = "payment_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String(36), ForeignKey("shopping_accounts.id"), nullable=False, index=True)
    reference = Column(String(64), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(32), nullable=False)  # UPI, CARD, WALLET, COD
    status = Column(String(32), default="PENDING", nullable=False)  # PENDING, AUTHORIZED, SUCCESS, FAILED, EXPIRED
    instrument_hint = Column(String(128), nullable=True)  # e.g. "user@upi" or card last-4
    failure_reason = Column(String(256), nullable=True)
    order_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
