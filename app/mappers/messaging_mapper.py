# ================================================
# app/mappers/messaging_mapper.py
# ================================================
"""
Mappers pour la messagerie
"""
from app.models.messaging_entity import ConversationEntity, MessageEntity
from app.schemas.messaging import ConversationSchema, MessageSchema


class ConversationMapper:
    """Mapper pour les conversations"""

    @staticmethod
    def entity_to_schema(entity: ConversationEntity) -> ConversationSchema:
        """Convertit ConversationEntity vers ConversationSchema"""
        if not entity:
            return None

        return ConversationSchema(
            id=entity.id,
            buyer_id=entity.buyer_id,
            supplier_id=entity.supplier_id,
            order_id=entity.order_id,
            product_id=entity.product_id,
            subject=entity.subject,
            is_active=entity.is_active,
            is_archived=entity.is_archived,
            last_message_at=entity.last_message_at.strftime("%d/%m/%Y %H:%M") if entity.last_message_at else None,
            last_message_preview=entity.last_message_preview,
            unread_count_buyer=entity.unread_count_buyer,
            unread_count_supplier=entity.unread_count_supplier,
            created_at=entity.created_at.strftime("%d/%m/%Y %H:%M") if entity.created_at else None,
            updated_at=entity.updated_at.strftime("%d/%m/%Y %H:%M") if entity.updated_at else None
        )


class MessageMapper:
    """Mapper pour les messages"""

    @staticmethod
    def entity_to_schema(entity: MessageEntity) -> MessageSchema:
        """Convertit MessageEntity vers MessageSchema"""
        if not entity:
            return None

        return MessageSchema(
            id=entity.id,
            conversation_id=entity.conversation_id,
            sender_id=entity.sender_id,
            content=entity.content,
            attachments=entity.attachments if entity.attachments else [],
            status=entity.status.value if entity.status else "sent",
            is_read=entity.is_read,
            read_at=entity.read_at.strftime("%d/%m/%Y %H:%M") if entity.read_at else None,
            reply_to_message_id=entity.reply_to_message_id,
            is_system_message=entity.is_system_message,
            created_at=entity.created_at.strftime("%d/%m/%Y %H:%M") if entity.created_at else None,
            updated_at=entity.updated_at.strftime("%d/%m/%Y %H:%M") if entity.updated_at else None
        )