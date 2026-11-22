"""Test Suite for Shopping, Isolated Cart, and Best-Offer Engine."""
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.accounts.manager import MultiAccountManager
from backend.api.cart import CartService
from backend.api.checkout import CheckoutService
from backend.api.orders import OrderService
from backend.api.products import ProductService
from backend.api.search import SearchService
from backend.database.models import Base, Offer, Product, User
from backend.offers.engine import BestOfferEngine


@pytest.fixture
def shop_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        user = User(id="user_shop_test")
        db.add(user)

        # Seed products
        p1 = Product(
            id="p1",
            name="Amul Milk",
            brand="Amul",
            category="Dairy",
            price=30.0,
            original_price=30.0,
            availability=True,
            stock_quantity=10,
        )
        p2 = Product(
            id="p2",
            name="Dark Chocolate",
            brand="Cadbury",
            category="Snacks",
            price=200.0,
            original_price=250.0,
            discount_percent=20,
            availability=True,
            stock_quantity=20,
        )
        db.add_all([p1, p2])

        # Seed offers
        off1 = Offer(
            id="off1",
            code="FLAT50",
            title="Flat ₹50 Off",
            offer_type="FLAT",
            discount_value=50.0,
            min_cart_value=150.0,
            is_active=True,
        )
        off2 = Offer(
            id="off2",
            code="BIG20",
            title="20% Off",
            offer_type="PERCENTAGE",
            discount_value=20.0,
            min_cart_value=200.0,
            max_discount=100.0,
            is_active=True,
        )
        db.add_all([off1, off2])
        db.commit()

        yield db
    finally:
        db.close()


def test_catalogue_and_search(shop_db):
    page = ProductService.get_page(shop_db)
    assert page["storeServiceableResponse"]["serviceable"] is True
    assert len(page["pageLayout"]["widgets"]) > 0

    search_res = SearchService.search_products(shop_db, "Milk")
    assert len(search_res["items"]) == 1
    assert search_res["items"][0]["name"] == "Amul Milk"


def test_isolated_carts_between_accounts(shop_db):
    acc1_res = MultiAccountManager.add_account(shop_db, "user_shop_test", "9876500001", "Acc 1")
    acc2_res = MultiAccountManager.add_account(shop_db, "user_shop_test", "9876500002", "Acc 2")

    acc1_id = acc1_res["account"]["accountId"]
    acc2_id = acc2_res["account"]["accountId"]

    # Acc 1 adds p1
    CartService.add_to_cart(shop_db, acc1_id, "p1", 2)
    cart1 = CartService.get_cart_details(shop_db, acc1_id)
    assert cart1["itemCount"] == 2
    assert cart1["cartTotal"] == 60.0

    # Acc 2 cart must be isolated and completely empty
    cart2 = CartService.get_cart_details(shop_db, acc2_id)
    assert cart2["itemCount"] == 0
    assert cart2["cartTotal"] == 0.0

    # Acc 2 adds p2
    CartService.add_to_cart(shop_db, acc2_id, "p2", 1)
    cart2_updated = CartService.get_cart_details(shop_db, acc2_id)
    assert cart2_updated["itemCount"] == 1
    assert cart2_updated["cartTotal"] == 200.0


def test_best_offer_engine_optimization(shop_db):
    acc_res = MultiAccountManager.add_account(shop_db, "user_shop_test", "9876500003", "Offer Acc")
    acc_id = acc_res["account"]["accountId"]

    # Cart = 2 x p2 = ₹400
    CartService.add_to_cart(shop_db, acc_id, "p2", 2)

    # Offer A: FLAT50 gives ₹50 off
    # Offer B: BIG20 gives 20% of ₹400 = ₹80 off
    # BestOfferEngine must recommend BIG20!
    eval_res = BestOfferEngine.evaluate_best_offer(shop_db, acc_id)
    assert eval_res["hasEligibleOffer"] is True
    assert eval_res["recommendedOffer"]["code"] == "BIG20"
    assert eval_res["recommendedOffer"]["discountAmount"] == 80.0

    # Auto Apply
    apply_res = BestOfferEngine.auto_apply_best_offer(shop_db, acc_id)
    assert apply_res["success"] is True
    assert apply_res["appliedOffer"]["code"] == "BIG20"


def test_checkout_and_order_flow(shop_db):
    acc_res = MultiAccountManager.add_account(shop_db, "user_shop_test", "9876500004", "Order Acc")
    acc_id = acc_res["account"]["accountId"]

    CartService.add_to_cart(shop_db, acc_id, "p2", 1)

    summary = CheckoutService.get_checkout_summary(shop_db, acc_id, coupon_code="FLAT50")
    assert summary["valid"] is True
    assert summary["billBreakdown"]["couponDiscount"] == 50.0

    order_res = OrderService.create_order(shop_db, acc_id, payment_method="UPI", coupon_code="FLAT50")
    assert order_res["success"] is True
    order_id = order_res["order"]["id"]

    # Cart should be cleared after order
    cart = CartService.get_cart_details(shop_db, acc_id)
    assert cart["itemCount"] == 0

    # Verify order details
    details = OrderService.get_order_details(shop_db, order_id)
    assert details["status"] == "PLACED"
    assert len(details["trackingSteps"]) == 4
