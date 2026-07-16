"""
Entités pour la messagerie et les notifications en temps réel
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, JSON, Enum as SQLEnum, func, \
    UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.enums import DevicePlatform, MessageStatus, NotificationType, PushProvider
from app.db.base import Base

# ================================================
# ENTITIES
# ================================================

class ConversationEntity(Base):
    """Entité pour les conversations entre acheteur et fournisseur"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)

    # Participants
    buyer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Contexte (optionnel)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"))
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"))

    # Métadonnées
    subject = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)

    # Dernière activité
    last_message_at = Column(DateTime(timezone=True))
    last_message_preview = Column(String(200))  # Aperçu du dernier message

    # Compteurs non lus (dénormalisés pour performance)
    unread_count_buyer = Column(Integer, default=0)
    unread_count_supplier = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    buyer = relationship("UserEntity", foreign_keys=[buyer_id], back_populates="buyer_conversations")
    supplier = relationship("UserEntity", foreign_keys=[supplier_id], back_populates="supplier_conversations")
    order = relationship("OrderEntity")
    product = relationship("ProductEntity")
    messages = relationship("MessageEntity", back_populates="conversation", cascade="all, delete-orphan")

    # Contrainte d'unicité : une conversation est identifiée par le couple
    # (acheteur, fournisseur) ET son contexte (commande / produit). Deux
    # demandes sur des produits différents avec le même fournisseur sont donc
    # deux fils distincts.
    __table_args__ = (
        UniqueConstraint('buyer_id', 'supplier_id', 'order_id', 'product_id', name='unique_conversation'),
    )


class MessageEntity(Base):
    """Entité pour les messages"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Contenu
    content = Column(Text, nullable=False)
    attachments = Column(JSON)  # Liste de fichiers joints

    # Statut
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.SENT, nullable=False)

    # Lecture
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))

    # Réponse à un message (threading)
    reply_to_message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"))

    # Métadonnées
    is_system_message = Column(Boolean, default=False)  # Message système (ex: "Commande confirmée")
    is_deleted = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    conversation = relationship("ConversationEntity", back_populates="messages")
    sender = relationship("UserEntity", foreign_keys=[sender_id])
    reply_to = relationship("MessageEntity", remote_side=[id])


class NotificationEntity(Base):
    """Entité pour les notifications système"""
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_notifications_user_event_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Type et contenu
    type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    # Données additionnelles (IDs, liens, etc.)
    data = Column(JSON)  # Ex: {"order_id": 123, "product_id": 45}

    # Clé d'idempotence (ex: "order:123:shipped"). Deux appels pour le même
    # évènement ne créent qu'une notification, même sous retry concurrent —
    # c'est la contrainte d'unicité qui l'impose, pas un check applicatif.
    # NULL pour les notifications sans évènement identifiable (les NULL ne
    # collisionnent pas entre eux dans un index unique).
    event_key = Column(String(120), index=True)

    # Métadonnées
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime(timezone=True))

    # Actions possibles (ex: boutons)
    action_url = Column(String(500))  # URL vers la ressource concernée
    action_label = Column(String(100))  # Libellé du bouton d'action

    # Expiration
    expires_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relations
    user = relationship("UserEntity", back_populates="notifications")


class DeviceTokenEntity(Base):
    """Jeton push d'un appareil, pour les notifications hors-app.

    Un utilisateur peut avoir plusieurs appareils. Le `token` est unique au niveau
    global : quand un appareil change de compte, la ligne est réassignée au nouveau
    `user_id` plutôt que dupliquée — sinon l'ancien propriétaire continuerait de
    recevoir les notifications du nouveau.
    """
    __tablename__ = "device_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    token = Column(String(255), nullable=False, unique=True, index=True)
    provider = Column(SQLEnum(PushProvider), nullable=False, default=PushProvider.EXPO)
    platform = Column(SQLEnum(DevicePlatform), nullable=False)

    # Permet de dédupliquer quand l'app est réinstallée et qu'Expo émet un token neuf.
    device_id = Column(String(128), index=True)

    # Passé à False sur `DeviceNotRegistered` renvoyé par le relais push.
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relations
    user = relationship("UserEntity", back_populates="device_tokens")


class UserPresenceEntity(Base):
    """Entité pour gérer la présence en ligne des utilisateurs"""
    __tablename__ = "user_presence"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Statut
    is_online = Column(Boolean, default=False)
    status = Column(String(50), default="offline")  # online, away, busy, offline

    # Dernière activité
    last_seen_at = Column(DateTime(timezone=True))
    last_activity_at = Column(DateTime(timezone=True))

    # Connexion WebSocket
    connection_id = Column(String(255))  # ID de la connexion WebSocket
    device_info = Column(JSON)  # Informations sur l'appareil

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    user = relationship("UserEntity", back_populates="presence")