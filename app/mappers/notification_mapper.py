# app/mappers/notification_mapper.py
"""
Mapper pour les notifications.
"""
from app.models.messaging_entity import NotificationEntity
from app.schemas.notification import NotificationSchema


class NotificationMapper:
    """Mapper NotificationEntity <-> NotificationSchema."""

    @staticmethod
    def entity_to_schema(entity: NotificationEntity) -> NotificationSchema:
        if not entity:
            return None

        return NotificationSchema(
            id=entity.id,
            user_id=entity.user_id,
            type=entity.type,
            title=entity.title,
            message=entity.message,
            data=entity.data if entity.data else {},
            is_read=entity.is_read,
            read_at=entity.read_at.strftime("%d/%m/%Y %H:%M") if entity.read_at else None,
            action_url=entity.action_url,
            action_label=entity.action_label,
            expires_at=entity.expires_at.strftime("%d/%m/%Y %H:%M") if entity.expires_at else None,
            created_at=entity.created_at.strftime("%d/%m/%Y %H:%M") if entity.created_at else None,
        )
