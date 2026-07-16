# ================================================
# app/repositories/messaging_repo.py
# ================================================
"""
Repositories pour la messagerie
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, case, func
from app.models.messaging_entity import ConversationEntity, MessageEntity, UserPresenceEntity
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository):
    """Repository pour les conversations"""

    def __init__(self, db: Session):
        super().__init__(db, ConversationEntity)

    def get_conversation_between_users(
            self,
            user1_id: int,
            user2_id: int,
            order_id: Optional[int] = None,
            product_id: Optional[int] = None
    ) -> Optional[ConversationEntity]:
        """Récupérer une conversation entre deux utilisateurs.

        Le contexte (order_id / product_id) fait partie de l'identité de la
        conversation : une demande sur le produit A et une demande sur le
        produit B avec le même fournisseur sont deux fils distincts. Les
        filtres sont symétriques (NULL == "sans contexte") pour ne pas
        rattacher une conversation produit à une conversation générale.
        """
        query = self.db.query(ConversationEntity).filter(
            or_(
                and_(
                    ConversationEntity.buyer_id == user1_id,
                    ConversationEntity.supplier_id == user2_id
                ),
                and_(
                    ConversationEntity.buyer_id == user2_id,
                    ConversationEntity.supplier_id == user1_id
                )
            ),
            ConversationEntity.is_active == True
        )

        if order_id is not None:
            query = query.filter(ConversationEntity.order_id == order_id)
        else:
            query = query.filter(ConversationEntity.order_id.is_(None))

        if product_id is not None:
            query = query.filter(ConversationEntity.product_id == product_id)
        else:
            query = query.filter(ConversationEntity.product_id.is_(None))

        return query.first()

    def get_user_conversations(self, user_id: int) -> List[ConversationEntity]:
        """Récupérer toutes les conversations d'un utilisateur"""
        return (
            self.db.query(ConversationEntity)
            .filter(
                or_(
                    ConversationEntity.buyer_id == user_id,
                    ConversationEntity.supplier_id == user_id
                ),
                ConversationEntity.is_active == True
            )
            .order_by(ConversationEntity.last_message_at.desc())
            .all()
        )

    def get_total_unread_messages(self, user_id: int, role: Optional[str] = None) -> int:
        """Somme des messages non lus de l'utilisateur, tous fils confondus.

        Source autoritative du badge « Messages » : les compteurs dénormalisés sur
        la conversation, et non un comptage des notifications `new_message` — les
        deux divergent dès qu'un message est lu depuis le web.

        `role` ('buyer' | 'supplier') restreint au périmètre de l'espace actif, pour
        un utilisateur qui cumule les deux rôles (cf. T5).
        """
        as_buyer = func.coalesce(
            func.sum(
                case(
                    (ConversationEntity.buyer_id == user_id, ConversationEntity.unread_count_buyer),
                    else_=0,
                )
            ),
            0,
        )
        as_supplier = func.coalesce(
            func.sum(
                case(
                    (ConversationEntity.supplier_id == user_id, ConversationEntity.unread_count_supplier),
                    else_=0,
                )
            ),
            0,
        )

        if role == "buyer":
            expression, participant = as_buyer, ConversationEntity.buyer_id == user_id
        elif role == "supplier":
            expression, participant = as_supplier, ConversationEntity.supplier_id == user_id
        else:
            expression = as_buyer + as_supplier
            participant = or_(
                ConversationEntity.buyer_id == user_id,
                ConversationEntity.supplier_id == user_id,
            )

        total = (
            self.db.query(expression)
            .filter(participant, ConversationEntity.is_active == True)
            .scalar()
        )
        return int(total or 0)

    def get_unread_conversations_count(self, user_id: int) -> int:
        """Compter les conversations avec des messages non lus"""
        return (
            self.db.query(ConversationEntity)
            .filter(
                or_(
                    and_(
                        ConversationEntity.buyer_id == user_id,
                        ConversationEntity.unread_count_buyer > 0
                    ),
                    and_(
                        ConversationEntity.supplier_id == user_id,
                        ConversationEntity.unread_count_supplier > 0
                    )
                ),
                ConversationEntity.is_active == True
            )
            .count()
        )


class MessageRepository(BaseRepository):
    """Repository pour les messages"""

    def __init__(self, db: Session):
        super().__init__(db, MessageEntity)

    def get_by_conversation(
            self,
            conversation_id: int,
            limit: int = 50,
            offset: int = 0
    ) -> List[MessageEntity]:
        """Récupérer les messages d'une conversation"""
        return (
            self.db.query(MessageEntity)
            .filter(
                MessageEntity.conversation_id == conversation_id,
                MessageEntity.is_deleted == False
            )
            .order_by(MessageEntity.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def get_unread_count(self, conversation_id: int, user_id: int) -> int:
        """Compter les messages non lus pour un utilisateur"""
        return (
            self.db.query(MessageEntity)
            .filter(
                MessageEntity.conversation_id == conversation_id,
                MessageEntity.sender_id != user_id,
                MessageEntity.is_read == False,
                MessageEntity.is_deleted == False
            )
            .count()
        )


class UserPresenceRepository(BaseRepository):
    """Repository pour la présence utilisateur"""

    def __init__(self, db: Session):
        super().__init__(db, UserPresenceEntity)

    def get_by_user_id(self, user_id: int) -> Optional[UserPresenceEntity]:
        """Récupérer la présence d'un utilisateur"""
        return (
            self.db.query(UserPresenceEntity)
            .filter(UserPresenceEntity.user_id == user_id)
            .first()
        )

    def update_presence(
            self,
            user_id: int,
            is_online: bool,
            connection_id: Optional[str] = None
    ) -> UserPresenceEntity:
        """Mettre à jour la présence d'un utilisateur"""
        from datetime import datetime

        presence = self.get_by_user_id(user_id)

        if presence:
            self.update(
                presence.id,
                is_online=is_online,
                status="online" if is_online else "offline",
                last_seen_at=datetime.now(),
                connection_id=connection_id
            )
        else:
            presence = self.create(
                user_id=user_id,
                is_online=is_online,
                status="online" if is_online else "offline",
                last_seen_at=datetime.now(),
                connection_id=connection_id
            )

        return presence