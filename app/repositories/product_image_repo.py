# ================================================
# app/repositories/product_image_repo.py
# ================================================
"""
Repository pour gérer les images de produits
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.product_image_entity import ProductImageEntity
from app.repositories.base import BaseRepository


class ProductImageRepository(BaseRepository):
    """Repository pour les images de produits"""

    def __init__(self, db: Session):
        super().__init__(db, ProductImageEntity)

    def get_by_product_id(self, product_id: int) -> List[ProductImageEntity]:
        """Récupérer toutes les images d'un produit"""
        return (
            self.db.query(ProductImageEntity)
            .filter(
                ProductImageEntity.product_id == product_id,
                ProductImageEntity.is_deleted == False
            )
            .order_by(ProductImageEntity.display_order)
            .all()
        )

    def get_primary_image(self, product_id: int) -> Optional[ProductImageEntity]:
        """Récupérer l'image principale d'un produit"""
        return (
            self.db.query(ProductImageEntity)
            .filter(
                ProductImageEntity.product_id == product_id,
                ProductImageEntity.is_primary == True,
                ProductImageEntity.is_deleted == False
            )
            .first()
        )

    def set_as_primary(self, image_id: int, product_id: int) -> None:
        """Définir une image comme principale"""
        # D'abord, retirer le flag primary de toutes les images
        self.db.query(ProductImageEntity).filter(
            ProductImageEntity.product_id == product_id
        ).update({"is_primary": False})

        # Ensuite, définir l'image sélectionnée comme principale
        self.db.query(ProductImageEntity).filter(
            ProductImageEntity.id == image_id
        ).update({"is_primary": True})

        self.db.commit()

    def reorder_images(self, image_orders: dict) -> None:
        """Réorganiser les images (dict: {image_id: order})"""
        for image_id, order in image_orders.items():
            self.db.query(ProductImageEntity).filter(
                ProductImageEntity.id == image_id
            ).update({"display_order": order})

        self.db.commit()

    def delete_by_product_id(self, product_id: int) -> int:
        """Supprimer toutes les images d'un produit (soft delete)"""
        result = self.db.query(ProductImageEntity).filter(
            ProductImageEntity.product_id == product_id
        ).update({"is_deleted": True})

        self.db.commit()
        return result