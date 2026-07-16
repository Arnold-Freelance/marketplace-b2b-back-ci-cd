"""
Entité pour gérer les images des produits
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class ProductImageEntity(Base):
    """Entité pour les images de produits"""
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    image_url = Column(String(500), nullable=False)  # URL de l'image originale
    thumbnail_url = Column(String(500))  # URL de la miniature
    display_order = Column(Integer, default=0)  # Ordre d'affichage
    is_primary = Column(Boolean, default=False)  # Image principale
    alt_text = Column(String(255))  # Texte alternatif pour SEO
    file_name = Column(String(255))  # Nom du fichier
    file_size = Column(Integer)  # Taille en bytes
    width = Column(Integer)  # Largeur en pixels
    height = Column(Integer)  # Hauteur en pixels
    is_deleted = Column(Boolean, default=False)
    created_by = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    product = relationship("ProductEntity", back_populates="product_images")