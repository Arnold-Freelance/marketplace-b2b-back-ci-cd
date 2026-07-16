# app/mappers/device_token_mapper.py
"""
Mapper pour les jetons push.
"""
from app.models.messaging_entity import DeviceTokenEntity
from app.schemas.notification import DeviceTokenSchema


class DeviceTokenMapper:
    """Mapper DeviceTokenEntity <-> DeviceTokenSchema."""

    @staticmethod
    def entity_to_schema(entity: DeviceTokenEntity) -> DeviceTokenSchema:
        if not entity:
            return None

        return DeviceTokenSchema(
            id=entity.id,
            user_id=entity.user_id,
            token=entity.token,
            platform=entity.platform,
            provider=entity.provider,
            device_id=entity.device_id,
            is_active=entity.is_active,
            created_at=entity.created_at.strftime("%d/%m/%Y %H:%M") if entity.created_at else None,
            last_used_at=entity.last_used_at.strftime("%d/%m/%Y %H:%M") if entity.last_used_at else None,
        )
