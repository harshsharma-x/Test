"""Database engine, session management, and initial data seeding."""
from __future__ import annotations

import os
import uuid
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database.crypto import encrypt_data
from backend.database.models import (
    Base,
    Offer,
    Product,
    ShoppingAccount,
    ShoppingCart,
    User,
)
from backend.database.schema_sync import sync_schema

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite:///./shopping_platform.db"
)

# SQLite concurrency configuration
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


INITIAL_PRODUCTS = [
    {
        "external_product_id": "zepto_prod_001",
        "name": "Amul Taaza Toned Fresh Milk",
        "brand": "Amul",
        "category": "Dairy & Breakfast",
        "price": 28.0,
        "original_price": 30.0,
        "discount_percent": 7,
        "unit": "500 ml",
        "image_url": "https://cdn.zeptonow.com/production/ik-seo/tr:w-600,cm-pad_resize/cms/product_variant/amul_taaza.jpg",
        "availability": True,
        "stock_quantity": 85,
        "rating": 4.8,
        "description": "Homogenised toned milk with 3.0% fat and 8.5% SNF.",
    },
    {
        "external_product_id": "zepto_prod_002",
        "name": "Fresh Alphonso Mangoes (Devgad / Ratnagiri)",
        "brand": "Fresh Produce",
        "category": "Fruits & Vegetables",
        "price": 499.0,
        "original_price": 699.0,
        "discount_percent": 29,
        "unit": "6 pcs (Approx. 1.2 kg)",
        "image_url": "https://cdn.zeptonow.com/production/ik-seo/tr:w-600,cm-pad_resize/cms/product_variant/alphonso_mango.jpg",
        "availability": True,
        "stock_quantity": 40,
        "rating": 4.9,
        "description": "Naturally ripened hand-picked premium Alphonso mangoes.",
    },
    {
        "external_product_id": "zepto_prod_003",
        "name": "Kwality Wall's Magnum Pistachio Ice Cream Stick",
        "brand": "Kwality Wall's",
        "category": "Ice Creams & Desserts",
        "price": 95.0,
        "original_price": 105.0,
        "discount_percent": 10,
        "unit": "80 ml",
        "image_url": "https://cdn.zeptonow.com/production/ik-seo/tr:w-600,cm-pad_resize/cms/product_variant/a359a606-86e7-4b8c-ac8f-67571165467e.jpg",
        "availability": True,
        "stock_quantity": 60,
        "rating": 4.7,
        "description": "Velvety smooth pistachio ice cream coated in thick crackling Belgian chocolate.",
    },
    {
        "external_product_id": "zepto_prod_004",
        "name": "Lay's India's Magic Masala Potato Chips",
        "brand": "Lay's",
        "category": "Snacks & Munchies",
        "price": 20.0,
        "original_price": 20.0,
        "discount_percent": 0,
        "unit": "50 g",
        "image_url": "https://cdn.zeptonow.com/production/ik-seo/tr:w-600,cm-pad_resize/cms/product_variant/lays_masala.jpg",
        "availability": True,
        "stock_quantity": 120,
        "rating": 4.6,
        "description": "Crispy golden sliced potatoes dusted with aromatic spicy masala seasoning.",
    },
    {
        "external_product_id": "zepto_prod_005",
        "name": "Coca-Cola Zero Sugar Can",
        "brand": "Coca-Cola",
        "category": "Cold Drinks & Juices",
        "price": 40.0,
        "original_price": 40.0,
        "discount_percent": 0,
        "unit": "300 ml",
        "image_url": "https://cdn.zeptonow.com/production/ik-seo/tr:w-600,cm-pad_resize/cms/product_variant/coca_cola_zero.jpg",
        "availability": True,
        "stock_quantity": 90,
        "rating": 4.5,
        "description": "Crisp, delicious, refreshing sparkling beverage with zero sugar and zero calories.",
    },
    {
        "external_product_id": "zepto_prod_006",
        "name": "Nutella Hazelnut Cocoa Spread",
        "brand": "Ferrero",
        "category": "Dairy & Breakfast",
        "price": 349.0,
        "original_price": 420.0,
        "discount_percent": 17,
        "unit": "350 g",
        "image_url": "https://cdn.zeptonow.com/production/ik-seo/tr:w-600,cm-pad_resize/cms/product_variant/nutella_spread.jpg",
        "availability": True,
        "stock_quantity": 35,
        "rating": 4.9,
        "description": "The original hazelnut chocolate spread made with quality selected ingredients.",
    },
    {
        "external_product_id": "zepto_prod_007",
        "name": "Nescafe Classic Instant Coffee",
        "brand": "Nescafe",
        "category": "Tea & Coffee",
        "price": 185.0,
        "original_price": 210.0,
        "discount_percent": 12,
        "unit": "100 g Jar",
        "image_url": "https://cdn.zeptonow.com/production/ik-seo/tr:w-600,cm-pad_resize/cms/product_variant/nescafe_classic.jpg",
        "availability": True,
        "stock_quantity": 50,
        "rating": 4.7,
        "description": "100% pure natural coffee beans roasted to perfection for an invigorating aroma.",
    },
    {
        "external_product_id": "zepto_prod_008",
        "name": "Maggi 2-Minute Instant Noodles",
        "brand": "Nestle",
        "category": "Instant & Frozen Food",
        "price": 56.0,
        "original_price": 60.0,
        "discount_percent": 7,
        "unit": "Pack of 4 (280 g)",
        "image_url": "https://cdn.zeptonow.com/production/ik-seo/tr:w-600,cm-pad_resize/cms/product_variant/maggi_noodles.jpg",
        "availability": True,
        "stock_quantity": 110,
        "rating": 4.8,
        "description": "India's favorite instant noodles infused with roasted spices for that authentic masala taste.",
    },
]

INITIAL_OFFERS = [
    {
        "external_offer_id": "off_welcome_100",
        "code": "WELCOME100",
        "title": "Flat ₹100 Off on First Order",
        "description": "Get flat ₹100 instant discount on cart values above ₹399.",
        "offer_type": "FLAT",
        "discount_value": 100.0,
        "min_cart_value": 399.0,
        "max_discount": 100.0,
        "is_active": True,
    },
    {
        "external_offer_id": "off_super_20",
        "code": "SUPER20",
        "title": "20% Off Big Savings",
        "description": "Save 20% up to ₹150 on your cart of ₹499 or more.",
        "offer_type": "PERCENTAGE",
        "discount_value": 20.0,
        "min_cart_value": 499.0,
        "max_discount": 150.0,
        "is_active": True,
    },
    {
        "external_offer_id": "off_flat_50",
        "code": "ZEPTO50",
        "title": "₹50 Instant Cashback Discount",
        "description": "Flat ₹50 off on carts above ₹199.",
        "offer_type": "FLAT",
        "discount_value": 50.0,
        "min_cart_value": 199.0,
        "max_discount": 50.0,
        "is_active": True,
    },
    {
        "external_offer_id": "off_freedel",
        "code": "FREEDEL",
        "title": "Free Instant 10-Min Delivery",
        "description": "Zero delivery charges on all orders above ₹149.",
        "offer_type": "FREE_DELIVERY",
        "discount_value": 25.0,
        "min_cart_value": 149.0,
        "max_discount": 25.0,
        "is_active": True,
    },
]


def init_db() -> None:
    """Initialize schema, apply forward migrations, and seed initial data."""
    Base.metadata.create_all(bind=engine)
    # create_all never alters pre-existing tables - add any newly required columns.
    sync_schema(engine)

    with SessionLocal() as session:
        # Check products
        if not session.query(Product).first():
            for p in INITIAL_PRODUCTS:
                session.add(Product(**p))

        # Check offers
        if not session.query(Offer).first():
            for off in INITIAL_OFFERS:
                session.add(Offer(**off))

        # Check default user & shopping accounts
        user = session.query(User).first()
        if not user:
            user = User(id="user_master_default", telegram_id="default_user")
            session.add(user)
            session.flush()

            # Account 1: Personal
            acc1 = ShoppingAccount(
                id=str(uuid.uuid4()),
                user_id=user.id,
                encrypted_mobile=encrypt_data("9876542168") or "",
                display_name="Personal Account",
                status="ACTIVE",
                is_default=True,
            )
            session.add(acc1)
            session.flush()

            cart1 = ShoppingCart(id=str(uuid.uuid4()), account_id=acc1.id)
            session.add(cart1)

            # Account 2: Secondary / Work
            acc2 = ShoppingAccount(
                id=str(uuid.uuid4()),
                user_id=user.id,
                encrypted_mobile=encrypt_data("9876598765") or "",
                display_name="Secondary Account",
                status="ACTIVE",
                is_default=False,
            )
            session.add(acc2)
            session.flush()

            cart2 = ShoppingCart(id=str(uuid.uuid4()), account_id=acc2.id)
            session.add(cart2)

        session.commit()
