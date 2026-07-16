# ================================================
# app/mappers/cart_mapper.py
# ================================================
"""
Mapper pour les paniers
"""
from app.models.order_entity import CartEntity, CartItemEntity
from app.schemas.cart import CartSchema, CartItemSchema


class CartMapper:
    """Mapper pour le panier"""

    @staticmethod
    def entity_to_schema(entity: CartEntity) -> CartSchema:
        """Convertit CartEntity vers CartSchema"""
        if not entity:
            return None

        cart_items = []
        if entity.cart_items:
            cart_items = [
                CartItemSchema(
                    id=item.id,
                    cart_id=item.cart_id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    subtotal=item.subtotal,
                    created_at=item.created_at.strftime("%d/%m/%Y %H:%M") if item.created_at else None,
                    updated_at=item.updated_at.strftime("%d/%m/%Y %H:%M") if item.updated_at else None
                )
                for item in entity.cart_items
            ]

        return CartSchema(
            id=entity.id,
            user_id=entity.user_id,
            is_active=entity.is_active,
            session_id=entity.session_id,
            cart_items=cart_items,
            created_at=entity.created_at.strftime("%d/%m/%Y %H:%M") if entity.created_at else None,
            updated_at=entity.updated_at.strftime("%d/%m/%Y %H:%M") if entity.updated_at else None
        )
