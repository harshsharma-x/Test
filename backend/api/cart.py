"""Cart API: Multi-account isolated cart management, additions, removals, validation."""
from __future__ import annotations

import uuid
from typing import Any, Dict
from sqlalchemy.orm import Session

from backend.database.models import Product, ShoppingCart, ShoppingCartItem


class CartService:
    @staticmethod
    def get_or_create_cart(db: Session, account_id: str) -> ShoppingCart:
        cart = db.query(ShoppingCart).filter(ShoppingCart.account_id == account_id).first()
        if not cart:
            cart = ShoppingCart(id=str(uuid.uuid4()), account_id=account_id)
            db.add(cart)
            db.commit()
            db.refresh(cart)
        return cart

    @staticmethod
    def get_cart_details(db: Session, account_id: str) -> Dict[str, Any]:
        """Cart overview matching POST /cfs/api/v1/cart/create response."""
        cart = CartService.get_or_create_cart(db, account_id)
        items = (
            db.query(ShoppingCartItem)
            .filter(ShoppingCartItem.cart_id == cart.id)
            .all()
        )

        item_list = []
        mrp_total = 0.0
        selling_total = 0.0

        for it in items:
            p = db.query(Product).filter(Product.id == it.product_id).first()
            if not p:
                continue
            item_mrp = p.original_price * it.quantity
            item_selling = p.price * it.quantity
            mrp_total += item_mrp
            selling_total += item_selling

            item_list.append(
                {
                    "id": it.id,
                    "productId": p.id,
                    "name": p.name,
                    "brand": p.brand,
                    "unit": p.unit,
                    "price": p.price,
                    "originalPrice": p.original_price,
                    "discountPercent": p.discount_percent,
                    "quantity": it.quantity,
                    "imageUrl": p.image_url,
                    "total": item_selling,
                }
            )

        item_discount = mrp_total - selling_total
        # Delivery fee: ₹25 if cart < ₹149, free if >= ₹149 (or empty)
        delivery_fee = 0.0 if (selling_total >= 149.0 or selling_total == 0) else 25.0
        free_delivery_threshold = 149.0
        amount_needed_for_free_del = max(0.0, free_delivery_threshold - selling_total) if selling_total > 0 else 0.0

        return {
            "cartId": cart.id,
            "accountId": account_id,
            "itemCount": sum(it.quantity for it in items),
            "items": item_list,
            "mrpTotal": round(mrp_total, 2),
            "itemDiscount": round(item_discount, 2),
            "cartTotal": round(selling_total, 2),
            "deliveryFee": round(delivery_fee, 2),
            "freeDeliveryThreshold": free_delivery_threshold,
            "amountNeededForFreeDelivery": round(amount_needed_for_free_del, 2),
            "finalPayable": round(selling_total + delivery_fee, 2),
        }

    @staticmethod
    def add_to_cart(db: Session, account_id: str, product_id: str, quantity: int = 1) -> Dict[str, Any]:
        cart = CartService.get_or_create_cart(db, account_id)
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return {"success": False, "error": "Product not found"}

        item = (
            db.query(ShoppingCartItem)
            .filter(ShoppingCartItem.cart_id == cart.id, ShoppingCartItem.product_id == product_id)
            .first()
        )
        if item:
            item.quantity += quantity
        else:
            item = ShoppingCartItem(id=str(uuid.uuid4()), cart_id=cart.id, product_id=product_id, quantity=quantity)
            db.add(item)

        db.commit()
        return CartService.get_cart_details(db, account_id)

    @staticmethod
    def update_quantity(db: Session, account_id: str, product_id: str, quantity: int) -> Dict[str, Any]:
        cart = CartService.get_or_create_cart(db, account_id)
        item = (
            db.query(ShoppingCartItem)
            .filter(ShoppingCartItem.cart_id == cart.id, ShoppingCartItem.product_id == product_id)
            .first()
        )
        if not item:
            if quantity > 0:
                return CartService.add_to_cart(db, account_id, product_id, quantity)
            return CartService.get_cart_details(db, account_id)

        if quantity <= 0:
            db.delete(item)
        else:
            item.quantity = quantity

        db.commit()
        return CartService.get_cart_details(db, account_id)

    @staticmethod
    def remove_from_cart(db: Session, account_id: str, product_id: str) -> Dict[str, Any]:
        return CartService.update_quantity(db, account_id, product_id, 0)

    @staticmethod
    def clear_cart(db: Session, account_id: str) -> Dict[str, Any]:
        cart = CartService.get_or_create_cart(db, account_id)
        db.query(ShoppingCartItem).filter(ShoppingCartItem.cart_id == cart.id).delete()
        db.commit()
        return CartService.get_cart_details(db, account_id)
