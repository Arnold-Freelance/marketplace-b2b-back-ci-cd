"""
Repository pour les paiements
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.order_entity import PaymentEntity, PaymentStatus
from app.repositories.base import BaseRepository


class PaymentRepository(BaseRepository):
    """Repository pour les paiements"""

    def __init__(self, db: Session):
        super().__init__(db, PaymentEntity)

    def get_by_transaction_id(self, transaction_id: str) -> Optional[PaymentEntity]:
        """Récupérer un paiement par son ID de transaction"""
        return (
            self.db.query(PaymentEntity)
            .filter(PaymentEntity.transaction_id == transaction_id)
            .first()
        )

    def get_by_order_id(self, order_id: int) -> List[PaymentEntity]:
        """Récupérer tous les paiements d'une commande"""
        return (
            self.db.query(PaymentEntity)
            .filter(PaymentEntity.order_id == order_id)
            .order_by(PaymentEntity.created_at.desc())
            .all()
        )

    def get_successful_payment(self, order_id: int) -> Optional[PaymentEntity]:
        """Récupérer le paiement réussi d'une commande"""
        return (
            self.db.query(PaymentEntity)
            .filter(
                PaymentEntity.order_id == order_id,
                PaymentEntity.payment_status == PaymentStatus.COMPLETED
            )
            .first()
        )