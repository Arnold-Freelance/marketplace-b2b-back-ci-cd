# app/models/product_document_entity.py
"""
Entité pour gérer les documents des produits (fiches techniques, certificats, etc.)
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base
class ProductDocumentEntity(Base):
    """Entité pour les documents de produits"""
    __tablename__ = "product_documents"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    document_url = Column(String(500), nullable=False)
    document_type = Column(String(50))  # 'fiche_technique', 'certificat', 'manuel', etc.
    title = Column(String(255), nullable=False)
    description = Column(String(500))
    file_name = Column(String(255))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    is_deleted = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    product = relationship("ProductEntity", back_populates="product_documents")
    creator = relationship("UserEntity", foreign_keys=[created_by])