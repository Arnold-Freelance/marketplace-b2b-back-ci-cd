# ================================================
# app/repositories/favorite_repo.py
# ================================================
"""
Repository pour les favoris"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.review_entity import FavoriteEntity
from app.repositories.base import BaseRepository


class FavoriteRepository(BaseRepository):
    """Repository pour les favoris"""

    def __init__(self, db: Session):
        super().__init__(db, FavoriteEntity)

    def get_by_user(self, user_id: int) -> List[FavoriteEntity]:
        """Récupérer tous les favoris d'un utilisateur"""
        return (
            self.db.query(FavoriteEntity)
            .filter(FavoriteEntity.user_id == user_id)
            .order_by(FavoriteEntity.created_at.desc())
            .all()
        )

    def get_by_user_and_product(
            self,
            user_id: int,
            product_id: int
    ) -> Optional[FavoriteEntity]:
        """Vérifier si un produit est dans les favoris"""
        return (
            self.db.query(FavoriteEntity)
            .filter(
                FavoriteEntity.user_id == user_id,
                FavoriteEntity.product_id == product_id
            )
            .first()
        )

    def count_by_product(self, product_id: int) -> int:
        """Compter combien de fois un produit est en favoris"""
        return (
            self.db.query(FavoriteEntity)
            .filter(FavoriteEntity.product_id == product_id)
            .count()
        )