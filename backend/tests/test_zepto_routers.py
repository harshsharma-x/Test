"""Integration Test Suite for Zepto-compatible Endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database.connection import get_db
from backend.database.models import Base, Product, User, ShoppingAccount, Offer
from backend.main import app

# In-memory database fixture
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_test_data():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSession()
    try:
        # Seed test user & account
        user = User(id="usr_test_zepto", telegram_id="tg_zepto_01")
        db.add(user)
        db.commit()

        account = ShoppingAccount(
            id="acc_test_zepto",
            user_id="usr_test_zepto",
            encrypted_mobile="gAAAAABtest",
            display_name="Zepto Tester",
            status="ACTIVE",
            is_default=True,
        )
        db.add(account)

        # Seed sample product
        p = Product(
            id="prod_onion_01",
            name="Fresh Onion 1kg",
            brand="Fresh Harvest",
            category="Fresh Vegetables",
            price=35.0,
            original_price=45.0,
            discount_percent=22,
            availability=True,
            stock_quantity=100,
            unit="1 kg",
            description="Farm fresh red onions",
            image_url="https://cdn.zeptonow.com/onion.png",
        )
        db.add(p)

        # Seed coupon
        coupon = Offer(
            id="off_super20",
            code="SUPER20",
            title="Flat 20% Off",
            description="Save 20% on all orders above 199",
            offer_type="PERCENTAGE",
            discount_value=20.0,
            min_cart_value=199.0,
            max_discount=100.0,
            is_active=True,
        )
        db.add(coupon)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


def test_csrf_token_endpoint(client):
    res = client.get("/api/auth/create-csrf-token")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "csrfToken" in data
    assert "csrfSecret" in data


def test_send_and_verify_otp(client):
    # Send OTP
    send_res = client.post("/api/v1/user/customer/send-otp-sms/", json={"mobileNumber": "9876542168"})
    assert send_res.status_code == 200
    assert send_res.json()["success"] is True

    # Verify OTP
    verify_res = client.post(
        "/api/auth/verify-otp",
        json={"mobileNumber": "9876542168", "otpToken": "123456", "fullName": "Test Customer"},
    )
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert "sessionToken" in v_data
    assert "zepto_session" in verify_res.cookies


def test_catalogue_get_page(client):
    res = client.get("/lms/api/v2/get_page?page_type=HOME&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert "widgets" in data
    assert "bottomNav" in data
    assert len(data["widgets"]) > 0


def test_search_endpoint(client):
    res = client.post(
        "/user-search-service/api/v3/search",
        json={"query": "Onion", "pageNumber": 0},
    )
    assert res.status_code == 200
    data = res.json()
    assert "products" in data
    assert len(data["products"]) >= 1
    assert data["products"][0]["product"]["name"] == "Fresh Onion 1kg"


def test_customer_info_and_wallet(client):
    # Authenticate to get session token
    verify_res = client.post(
        "/api/auth/verify-otp",
        json={"mobileNumber": "9876542168", "otpToken": "123456", "fullName": "Zepto Shopper"},
    )
    token = verify_res.json()["sessionToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # Customer info
    info_res = client.post("/api/v2/user/customer/info/", json={}, headers=headers)
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert "user" in info_data
    assert "userAggregate" in info_data

    # Wallet balances
    wallet_res = client.get("/api/v1/wallet-balances/total", headers=headers)
    assert wallet_res.status_code == 200
    assert "totalBalance" in wallet_res.json()

    # Pass overview
    pass_res = client.get("/api/v1/pass/overview", headers=headers)
    assert pass_res.status_code == 200
    assert "lifetimeSavings" in pass_res.json()

    # Referrals
    ref_res = client.get("/api/v1/user/customer/referrals/", headers=headers)
    assert ref_res.status_code == 200
    assert "referralCode" in ref_res.json()


def test_cart_and_coupons_flow(client):
    # Authenticate
    verify_res = client.post(
        "/api/auth/verify-otp",
        json={"mobileNumber": "9876542168", "otpToken": "123456"},
    )
    token = verify_res.json()["sessionToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # Add item to cart
    add_res = client.post(
        "/cfs/api/v1/cart/add",
        json={"storeProductId": "prod_onion_01", "quantity": 6},
        headers=headers,
    )
    assert add_res.status_code == 200
    cart_data = add_res.json()
    assert cart_data["cartItemCount"] == 6
    assert cart_data["grandTotalAmount"] > 0

    # List coupons
    coupons_res = client.get("/coupon-service/api/v1/coupons", headers=headers)
    assert coupons_res.status_code == 200
    coupons = coupons_res.json()["coupons"]
    assert len(coupons) >= 1

    # Apply coupon
    apply_res = client.post(
        "/coupon-service/api/v1/coupons/apply",
        json={"code": "SUPER20"},
        headers=headers,
    )
    assert apply_res.status_code == 200
    assert apply_res.json()["appliedCoupon"]["code"] == "SUPER20"


def test_quickpay_and_order_flow(client):
    # Authenticate
    verify_res = client.post(
        "/api/auth/verify-otp",
        json={"mobileNumber": "9876542168", "otpToken": "123456"},
    )
    token = verify_res.json()["sessionToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # QuickPay methods
    qp_res = client.post(
        "/payment-service/payment-listing-api/v1/quickpay",
        json={"amount": 21000},
        headers=headers,
    )
    assert qp_res.status_code == 200
    assert len(qp_res.json()["paymentMethods"]) >= 1

    # Place order
    order_res = client.post(
        "/order-service/api/v1/orders/create",
        json={"paymentMethod": "UPI"},
        headers=headers,
    )
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert "order" in order_data
    order_id = order_data["order"]["id"]

    # Order details
    details_res = client.post(
        "/pfs-postorder/api/v1/get-page/ORDER_DETAILS",
        json={"orderId": order_id},
        headers=headers,
    )
    assert details_res.status_code == 200
    assert details_res.json()["orderDetails"]["id"] == order_id


def test_graphql_gateway(client):
    res = client.post(
        "/api/v1/gateway/graphql/",
        json={"operationName": "GetUserInfo", "query": "query GetUserInfo { user { info { fullName } } }"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "data" in data
    assert "user" in data["data"]
    assert data["errors"] is None
