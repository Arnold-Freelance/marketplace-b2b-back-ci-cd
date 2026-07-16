"""
Repositories pour le panier
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.order_entity import CartEntity, CartItemEntity
from app.repositories.base import BaseRepository


class CartRepository(BaseRepository):
    """Repository pour les paniers"""

    def __init__(self, db: Session):
        super().__init__(db, CartEntity)

    def get_active_cart(self, user_id: int) -> Optional[CartEntity]:
        """Récupérer le panier actif d'un utilisateur"""
        return (
            self.db.query(CartEntity)
            .filter(
                CartEntity.user_id == user_id,
                CartEntity.is_active == True
            )
            .first()
        )

    def deactivate_old_carts(self, user_id: int) -> None:
        """Désactiver les anciens paniers d'un utilisateur"""
        self.db.query(CartEntity).filter(
            CartEntity.user_id == user_id,
            CartEntity.is_active == True
        ).update({"is_active": False})
        self.db.commit()


class CartItemRepository(BaseRepository):
    """Repository pour les items du panier"""

    def __init__(self, db: Session):
        super().__init__(db, CartItemEntity)

    def get_by_cart_and_product(
            self,
            cart_id: int,
            product_id: int
    ) -> Optional[CartItemEntity]:
        """Récupérer un item spécifique du panier"""
        return (
            self.db.query(CartItemEntity)
            .filter(
                CartItemEntity.cart_id == cart_id,
                CartItemEntity.product_id == product_id
            )
            .first()
        )

    def get_by_cart_id(self, cart_id: int) -> List[CartItemEntity]:
        """Récupérer tous les items d'un panier"""
        return (
            self.db.query(CartItemEntity)
            .filter(CartItemEntity.cart_id == cart_id)
            .all()
        )

    def delete_by_cart_id(self, cart_id: int) -> int:
        """Supprimer tous les items d'un panier"""
        result = (
            self.db.query(CartItemEntity)
            .filter(CartItemEntity.cart_id == cart_id)
            .delete()
        )
        self.db.commit()
        return result
