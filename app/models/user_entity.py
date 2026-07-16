# app/models/user_entity.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Numeric, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base
from app.core.enums import UserType, UserStatus, OrderStatus
from sqlalchemy.sql import func



class UserEntity(Base):
    """Entité User"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    user_type = Column(SQLEnum(UserType, name="user_type"), nullable=False)
    status = Column(SQLEnum(UserStatus, name="user_status"), default=UserStatus.pending)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Vérifications
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)

    # Relations
    company_profile = relationship("CompanyProfileEntity", back_populates="user", uselist=False)
    # Rôles multiples (T5). Un supplier possède aussi buyer ; le switch d'espace
    # est un changement de contexte frontend, les guards vérifient la présence.
    roles = relationship(
        "UserRoleEntity",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    products = relationship(
        "ProductEntity",
        back_populates="supplier",
        foreign_keys="ProductEntity.supplier_id",
    )
    buyer_orders = relationship("OrderEntity", foreign_keys="OrderEntity.buyer_id", back_populates="buyer")
    supplier_orders = relationship("OrderEntity", foreign_keys="OrderEntity.supplier_id", back_populates="supplier")
    carts = relationship("CartEntity", back_populates="user")

    # Relations pour la messagerie
    buyer_conversations = relationship(
        "ConversationEntity",
        foreign_keys="ConversationEntity.buyer_id",
        back_populates="buyer"
    )
    supplier_conversations = relationship(
        "ConversationEntity",
        foreign_keys="ConversationEntity.supplier_id",
        back_populates="supplier"
    )

    # Relations pour les notifications
    notifications = relationship("NotificationEntity", back_populates="user")
    device_tokens = relationship(
        "DeviceTokenEntity", back_populates="user", cascade="all, delete-orphan"
    )

    # Relation pour la présence
    presence = relationship("UserPresenceEntity", back_populates="user", uselist=False)

    # Relations pour les avis
    reviews_given = relationship(
        "ReviewEntity",
        foreign_keys="ReviewEntity.reviewer_id",
        back_populates="reviewer"
    )
    reviews_received = relationship(
        "ReviewEntity",
        foreign_keys="ReviewEntity.reviewed_id",
        back_populates="reviewed_user"
    )

    # Relations pour les favoris
    favorites = relationship("FavoriteEntity", back_populates="user")

    # Statistiques de réputation (calculées)
    @property
    def average_rating(self) -> float:
        '''Calcule la note moyenne du fournisseur'''
        if not self.reviews_received:
            return 0.0

        total_rating = sum(r.rating for r in self.reviews_received if not r.is_deleted)
        count = len([r for r in self.reviews_received if not r.is_deleted])

        return round(total_rating / count, 2) if count > 0 else 0.0

    @property
    def total_reviews_count(self) -> int:
        '''Nombre total d'avis reçus'''
        return len([r for r in self.reviews_received if not r.is_deleted])

    @property
    def role_names(self) -> list[str]:
        '''Liste des rôles de l'utilisateur (T5).

        Source de vérité : la table `user_roles`. Fallback défensif : si aucun
        rôle n'est encore enregistré (compte non migré), on dérive de
        `user_type` — un supplier obtenant aussi `buyer`.
        '''
        names = {r.role for r in self.roles} if self.roles else set()
        if not names and self.user_type is not None:
            names = {self.user_type.value}
            if self.user_type.value == "supplier":
                names.add("buyer")
        return sorted(names)


# Import en fin de module pour garantir le chargement de l'entité liée (et sa
# table dans Base.metadata) dès que UserEntity est importé — sans cycle :
# user_role_entity ne référence UserEntity que par chaîne.
from app.models.user_role_entity import UserRoleEntity  # noqa: E402,F401


# class OrderEntity(Base):
#     __tablename__ = "orders"
#
#     id = Column(Integer, primary_key=True, index=True)
#     order_number = Column(String(50), unique=True, nullable=False)
#     buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     supplier_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     subtotal = Column(Numeric(12, 2), nullable=False)
#     total_amount = Column(Numeric(12, 2), nullable=False)
#     currency = Column(String(3), default="XOF")
#     status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
#     shipping_address = Column(JSON)
#     buyer_notes = Column(Text)
#     supplier_notes = Column(Text)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
#
#     # Relations
#     buyer = relationship("UserEntity", foreign_keys=[buyer_id], back_populates="buyer_orders")
#     supplier = relationship("UserEntity", foreign_keys=[supplier_id], back_populates="supplier_orders")