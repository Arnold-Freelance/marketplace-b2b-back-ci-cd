"""
Mapper pour les favoris
"""
from app.models.review_entity import FavoriteEntity
from app.schemas.favorite import FavoriteSchema


class FavoriteMapper:
    """Mapper pour les favoris"""

    @staticmethod
    def entity_to_schema(entity: FavoriteEntity) -> FavoriteSchema:
        """Convertit FavoriteEntity vers FavoriteSchema"""
        if not entity:
            return None

        return FavoriteSchema(
            id=entity.id,
            user_id=entity.user_id,
            product_id=entity.product_id,
            notes=entity.notes,
            priority=entity.priority,
            notification_enabled=entity.notification_enabled,
            price_at_add=entity.price_at_add,
            created_at=entity.created_at.strftime("%d/%m/%Y %H:%M") if entity.created_at else None
        )