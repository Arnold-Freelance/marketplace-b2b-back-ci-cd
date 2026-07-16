"""
Entités pour les évaluations et la wishlist
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, CheckConstraint, UniqueConstraint, \
    func, Numeric
from sqlalchemy.orm import relationship
from app.db.base import Base


class ReviewEntity(Base):
    """Entité pour les avis et évaluations"""
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)

    # Références
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewed_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
                         index=True)  # Fournisseur évalué
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), index=True)

    # Évaluation
    rating = Column(Integer, nullable=False)  # 1 à 5
    title = Column(String(255))
    comment = Column(Text)

    # Critères d'évaluation détaillés (optionnels)
    quality_rating = Column(Integer)  # Qualité du produit (1-5)
    delivery_rating = Column(Integer)  # Rapidité de livraison (1-5)
    service_rating = Column(Integer)  # Service client (1-5)
    value_rating = Column(Integer)  # Rapport qualité/prix (1-5)

    # Métadonnées
    is_verified = Column(Boolean, default=False)  # Achat vérifié
    is_public = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)

    # Réponse du fournisseur
    supplier_response = Column(Text)
    supplier_response_at = Column(DateTime(timezone=True))

    # Utilité (votes)
    helpful_count = Column(Integer, default=0)
    not_helpful_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    order = relationship("OrderEntity")
    reviewer = relationship("UserEntity", foreign_keys=[reviewer_id], back_populates="reviews_given")
    reviewed_user = relationship("UserEntity", foreign_keys=[reviewed_id], back_populates="reviews_received")
    product = relationship("ProductEntity", back_populates="reviews")

    # Contraintes
    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
        CheckConstraint('quality_rating IS NULL OR (quality_rating >= 1 AND quality_rating <= 5)',
                        name='check_quality_rating'),
        CheckConstraint('delivery_rating IS NULL OR (delivery_rating >= 1 AND delivery_rating <= 5)',
                        name='check_delivery_rating'),
        CheckConstraint('service_rating IS NULL OR (service_rating >= 1 AND service_rating <= 5)',
                        name='check_service_rating'),
        CheckConstraint('value_rating IS NULL OR (value_rating >= 1 AND value_rating <= 5)', name='check_value_rating'),
        UniqueConstraint('order_id', 'reviewer_id', 'reviewed_id', name='unique_review_per_order'),
    )


class ReviewHelpfulVoteEntity(Base):
    """Entité pour les votes d'utilité des avis"""
    __tablename__ = "review_helpful_votes"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_helpful = Column(Boolean, nullable=False)  # True = utile, False = pas utile

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    review = relationship("ReviewEntity")
    user = relationship("UserEntity")

    # Contrainte d'unicité
    __table_args__ = (
        UniqueConstraint('review_id', 'user_id', name='unique_vote_per_review'),
    )


class FavoriteEntity(Base):
    """Entité pour les favoris/wishlist"""
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    # Métadonnées optionnelles
    notes = Column(Text)  # Notes personnelles
    priority = Column(Integer, default=0)  # Niveau de priorité (0-5)
    notification_enabled = Column(Boolean, default=True)  # Notifier si promotion/stock

    # Suivi du prix
    price_at_add = Column(Numeric(10, 2))  # Prix au moment de l'ajout

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relations
    user = relationship("UserEntity", back_populates="favorites")
    product = relationship("ProductEntity", back_populates="favorited_by")

    # Contrainte d'unicité
    __table_args__ = (
        UniqueConstraint('user_id', 'product_id', name='unique_favorite'),
    )