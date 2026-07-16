from sqlalchemy import Column, Integer, Numeric, JSON, Text, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base
from sqlalchemy.sql import func


class ProductEntity(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    description = Column(Text)
    short_description = Column(String(500))
    sku = Column(String(100))
    price = Column(Numeric(10, 2), nullable=False)
    # Prix de référence AVANT remise. Nul = pas de promotion en cours. Le prix
    # barré n'est affiché que si `original_price > price` — c'est la seule
    # définition d'une remise, il n'y a pas de champ « pourcentage » à tenir à jour.
    original_price = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), default="XOF")
    min_order_quantity = Column(Integer, default=1)
    stock_quantity = Column(Integer, default=0)
    unit = Column(String(50))
    # Surcharge de livraison pour un produit hors norme (volumineux, pondéreux).
    # Nul = on applique le barème de base du fournisseur.
    shipping_cost_override = Column(Numeric(10, 2), nullable=True)
    images = Column(JSON)
    attributes = Column(JSON)
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    views_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    # Traçabilité (T6) : dernier utilisateur ayant créé/modifié le produit.
    # Sert notamment à savoir quand un admin agit sur le produit d'un fournisseur.
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relations
    # `foreign_keys` explicite : products référence users deux fois (supplier_id
    # ET updated_by) → il faut lever l'ambiguïté du join.
    supplier = relationship(
        "UserEntity", back_populates="products", foreign_keys=[supplier_id]
    )
    category = relationship("CategoryEntity", back_populates="products")

    # NOUVELLES Relations pour images et documents
    product_images = relationship(
        "ProductImageEntity",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImageEntity.display_order"
    )
    # product_documents = relationship(
    #     "ProductDocumentEntity",
    #     back_populates="product",
    #     cascade="all, delete-orphan"
    # )

    # Relations
    reviews = relationship("ReviewEntity", back_populates="product")
    favorited_by = relationship("FavoriteEntity", back_populates="product")

    # Statistiques (calculées)
    @property
    def average_rating(self) -> float:
        '''Note moyenne du produit'''
        if not self.reviews:
            return 0.0

        valid_reviews = [r for r in self.reviews if not r.is_deleted and r.is_public]
        if not valid_reviews:
            return 0.0

        total_rating = sum(r.rating for r in valid_reviews)
        return round(total_rating / len(valid_reviews), 2)

    @property
    def reviews_count(self) -> int:
        '''Nombre d'avis du produit'''
        return len([r for r in self.reviews if not r.is_deleted and r.is_public])

    @property
    def favorites_count(self) -> int:
        '''Nombre de fois ajouté aux favoris'''
        return len(self.favorited_by)

    @property
    def rating_distribution(self) -> dict:
        '''Distribution des notes (1-5 étoiles)'''
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        valid_reviews = [r for r in self.reviews if not r.is_deleted and r.is_public]
        for review in valid_reviews:
            distribution[review.rating] += 1

        return distribution