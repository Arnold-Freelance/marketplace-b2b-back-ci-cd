from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.product_document_entity import ProductDocumentEntity
from app.repositories.base import BaseRepository

class ProductDocumentRepository(BaseRepository):
    """Repository pour les documents de produits"""

    def __init__(self, db: Session):
        super().__init__(db, ProductDocumentEntity)

    def get_by_product_id(self, product_id: int) -> List[ProductDocumentEntity]:
        """Récupérer tous les documents d'un produit"""
        return (
            self.db.query(ProductDocumentEntity)
            .filter(
                ProductDocumentEntity.product_id == product_id,
                ProductDocumentEntity.is_deleted == False
            )
            .all()
        )

    def get_by_type(self, product_id: int, document_type: str) -> List[ProductDocumentEntity]:
        """Récupérer les documents par type"""
        return (
            self.db.query(ProductDocumentEntity)
            .filter(
                ProductDocumentEntity.product_id == product_id,
                ProductDocumentEntity.document_type == document_type,
                ProductDocumentEntity.is_deleted == False
            )
            .all()
        )