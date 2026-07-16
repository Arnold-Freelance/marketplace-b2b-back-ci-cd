# app/models/order_entity.py
"""
Entités pour la gestion des commandes, paniers et paiements
"""
from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime, Text, JSON, Enum as SQLEnum, \
    func
from sqlalchemy.orm import relationship
from enum import Enum
from app.db.base import Base


# ================================================
# ENUMS
# ================================================

class OrderStatus(str, Enum):
    """Statuts d'une commande"""
    PENDING = "pending"  # En attente de confirmation
    CONFIRMED = "confirmed"  # Confirmée par le fournisseur
    PAID = "paid"  # Payée
    PROCESSING = "processing"  # En préparation
    SHIPPED = "shipped"  # Expédiée
    DELIVERED = "delivered"  # Livrée
    CANCELLED = "cancelled"  # Annulée
    REFUNDED = "refunded"  # Remboursée


class PaymentStatus(str, Enum):
    """Statuts de paiement"""
    PENDING = "pending"  # En attente
    PROCESSING = "processing"  # En cours de traitement
    COMPLETED = "completed"  # Complété
    FAILED = "failed"  # Échoué
    REFUNDED = "refunded"  # Remboursé
    CANCELLED = "cancelled"  # Annulé


class PaymentMethod(str, Enum):
    """Méthodes de paiement"""
    CARD = "card"  # Carte bancaire
    MOBILE_MONEY = "mobile_money"  # Mobile Money (Orange, MTN, Moov)
    BANK_TRANSFER = "bank_transfer"  # Virement bancaire
    CASH = "cash"  # Espèces (à la livraison)
    PAYPAL = "paypal"  # PayPal
    STRIPE = "stripe"  # Stripe


class ShippingMethod(str, Enum):
    """Méthodes de livraison"""
    STANDARD = "standard"  # Livraison standard (5-7 jours)
    EXPRESS = "express"  # Livraison express (2-3 jours)
    PICKUP = "pickup"  # Retrait en magasin
    SAME_DAY = "same_day"  # Livraison le jour même


# ================================================
# ENTITIES
# ================================================

class OrderEntity(Base):
    """Entité pour les commandes"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)

    # Acteurs
    buyer_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # Montants
    subtotal = Column(Numeric(12, 2), nullable=False)  # Sous-total (somme des items)
    shipping_cost = Column(Numeric(10, 2), default=0)  # Frais de livraison
    tax_amount = Column(Numeric(10, 2), default=0)  # TVA/Taxes
    discount_amount = Column(Numeric(10, 2), default=0)  # Réductions
    total_amount = Column(Numeric(12, 2), nullable=False)  # Montant total
    currency = Column(String(3), default="XOF")

    # Statuts
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)

    # Livraison
    shipping_method = Column(SQLEnum(ShippingMethod), default=ShippingMethod.STANDARD)
    shipping_address = Column(JSON)  # Adresse complète de livraison
    tracking_number = Column(String(100))  # Numéro de suivi
    estimated_delivery_date = Column(DateTime(timezone=True))
    actual_delivery_date = Column(DateTime(timezone=True))

    # Notes et commentaires
    buyer_notes = Column(Text)  # Notes de l'acheteur
    supplier_notes = Column(Text)  # Notes du fournisseur
    cancellation_reason = Column(Text)  # Raison d'annulation

    # Champ pour savoir si la commande a été évaluée
    is_reviewed = Column(Boolean, default=False)

    # Métadonnées
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    buyer = relationship("UserEntity", foreign_keys=[buyer_id], back_populates="buyer_orders")
    supplier = relationship("UserEntity", foreign_keys=[supplier_id], back_populates="supplier_orders")
    order_items = relationship("OrderItemEntity", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("PaymentEntity", back_populates="order", cascade="all, delete-orphan")
    status_history = relationship("OrderStatusHistoryEntity", back_populates="order", cascade="all, delete-orphan")


class OrderItemEntity(Base):
    """Entité pour les items d'une commande"""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)

    # Données au moment de la commande (snapshot)
    product_name = Column(String(255), nullable=False)
    product_sku = Column(String(100))
    product_image_url = Column(String(500))  # Image principale au moment de la commande

    # Quantités et prix
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)  # Prix unitaire au moment de la commande
    subtotal = Column(Numeric(12, 2), nullable=False)  # quantity * unit_price
    currency = Column(String(3), default="XOF")

    # Métadonnées produit
    product_attributes = Column(JSON)  # Attributs du produit au moment de la commande

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    order = relationship("OrderEntity", back_populates="order_items")
    product = relationship("ProductEntity")


class OrderStatusHistoryEntity(Base):
    """Historique des changements de statut d'une commande"""
    __tablename__ = "order_status_history"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)

    old_status = Column(SQLEnum(OrderStatus))
    new_status = Column(SQLEnum(OrderStatus), nullable=False)

    comment = Column(Text)  # Commentaire optionnel
    changed_by = Column(Integer, ForeignKey("users.id"))  # Qui a effectué le changement

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    order = relationship("OrderEntity", back_populates="status_history")
    user = relationship("UserEntity")


class PaymentEntity(Base):
    """Entité pour les paiements"""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)

    # Informations de paiement
    payment_method = Column(SQLEnum(PaymentMethod), nullable=False)
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="XOF")

    # Références externes
    transaction_id = Column(String(255), unique=True, index=True)  # ID de la transaction chez le provider
    payment_provider = Column(String(100))  # Stripe, PayPal, Orange Money, etc.

    # Détails supplémentaires
    payment_details = Column(JSON)  # Détails spécifiques au provider
    failure_reason = Column(Text)  # Raison de l'échec si applicable

    # Dates
    paid_at = Column(DateTime(timezone=True))
    refunded_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    order = relationship("OrderEntity", back_populates="payments")


class CartEntity(Base):
    """Entité pour les paniers d'achat"""
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Statut du panier
    is_active = Column(Boolean, default=True)  # Un seul panier actif par utilisateur

    # Métadonnées
    session_id = Column(String(255))  # Pour les paniers anonymes
    expires_at = Column(DateTime(timezone=True))  # Expiration du panier

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    user = relationship("UserEntity", back_populates="carts")
    cart_items = relationship("CartItemEntity", back_populates="cart", cascade="all, delete-orphan")


class CartItemEntity(Base):
    """Entité pour les items d'un panier"""
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    quantity = Column(Integer, nullable=False, default=1)

    # Données calculées (pour performance)
    unit_price = Column(Numeric(10, 2))  # Prix au moment de l'ajout
    subtotal = Column(Numeric(12, 2))  # quantity * unit_price

    # Champ pour savoir si la commande a été évaluée
    is_reviewed = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    cart = relationship("CartEntity", back_populates="cart_items")
    product = relationship("ProductEntity")


# class WishlistEntity(Base):
#     """Entité pour les listes de souhaits"""
#     __tablename__ = "wishlists"
#
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
#     product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
#
#     notes = Column(Text)  # Notes personnelles
#
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#
#     # Relations
#     user = relationship("UserEntity")
#     product = relationship("ProductEntity")
#
#     # Contrainte d'unicité
#     __table_args__ = (
#         {'sqlite_autoincrement': True},
#     )
