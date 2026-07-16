# ================================================
# app/repositories/order_repo.py
# ================================================
"""
Repositories pour les commandes
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.order_entity import OrderEntity, OrderItemEntity, OrderStatusHistoryEntity, OrderStatus
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository):
    """Repository pour les commandes"""

    def __init__(self, db: Session):
        super().__init__(db, OrderEntity)

    def get_by_order_number(self, order_number: str) -> Optional[OrderEntity]:
        """Récupérer une commande par son numéro"""
        return (
            self.db.query(OrderEntity)
            .filter(
                OrderEntity.order_number == order_number,
                OrderEntity.is_deleted == False
            )
            .first()
        )

    def get_by_buyer_id(self, buyer_id: int) -> List[OrderEntity]:
        """Récupérer toutes les commandes d'un acheteur"""
        return (
            self.db.query(OrderEntity)
            .filter(
                OrderEntity.buyer_id == buyer_id,
                OrderEntity.is_deleted == False
            )
            .order_by(OrderEntity.created_at.desc())
            .all()
        )

    def get_by_supplier_id(self, supplier_id: int) -> List[OrderEntity]:
        """Récupérer toutes les commandes d'un fournisseur"""
        return (
            self.db.query(OrderEntity)
            .filter(
                OrderEntity.supplier_id == supplier_id,
                OrderEntity.is_deleted == False
            )
            .order_by(OrderEntity.created_at.desc())
            .all()
        )

    def get_by_status(self, status: OrderStatus) -> List[OrderEntity]:
        """Récupérer les commandes par statut"""
        return (
            self.db.query(OrderEntity)
            .filter(
                OrderEntity.status == status,
                OrderEntity.is_deleted == False
            )
            .all()
        )

    def get_pending_orders(self, supplier_id: int) -> List[OrderEntity]:
        """Récupérer les commandes en attente d'un fournisseur"""
        return (
            self.db.query(OrderEntity)
            .filter(
                OrderEntity.supplier_id == supplier_id,
                OrderEntity.status == OrderStatus.PENDING,
                OrderEntity.is_deleted == False
            )
            .order_by(OrderEntity.created_at.desc())
            .all()
        )


class OrderItemRepository(BaseRepository):
    """Repository pour les items de commande"""

    def __init__(self, db: Session):
        super().__init__(db, OrderItemEntity)

    def get_by_order_id(self, order_id: int) -> List[OrderItemEntity]:
        """Récupérer tous les items d'une commande"""
        return (
            self.db.query(OrderItemEntity)
            .filter(OrderItemEntity.order_id == order_id)
            .all()
        )

    def get_by_product_id(self, product_id: int) -> List[OrderItemEntity]:
        """Récupérer tous les items contenant un produit"""
        return (
            self.db.query(OrderItemEntity)
            .filter(OrderItemEntity.product_id == product_id)
            .all()
        )


class OrderStatusHistoryRepository(BaseRepository):
    """Repository pour l'historique des statuts"""

    def __init__(self, db: Session):
        super().__init__(db, OrderStatusHistoryEntity)

    def get_by_order_id(self, order_id: int) -> List[OrderStatusHistoryEntity]:
        """Récupérer l'historique d'une commande"""
        return (
            self.db.query(OrderStatusHistoryEntity)
            .filter(OrderStatusHistoryEntity.order_id == order_id)
            .order_by(OrderStatusHistoryEntity.created_at.asc())
            .all()
        )