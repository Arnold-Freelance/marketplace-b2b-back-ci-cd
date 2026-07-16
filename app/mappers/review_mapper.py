# app/mappers/review_mapper.py
"""
Mapper pour les avis
"""
from app.models.review_entity import ReviewEntity
from app.schemas.review import ReviewSchema


class ReviewMapper:
    """Mapper pour les avis"""

    @staticmethod
    def entity_to_schema(entity: ReviewEntity) -> ReviewSchema:
        """Convertit ReviewEntity vers ReviewSchema"""
        if not entity:
            return None

        return ReviewSchema(
            id=entity.id,
            order_id=entity.order_id,
            reviewer_id=entity.reviewer_id,
            reviewed_id=entity.reviewed_id,
            product_id=entity.product_id,
            rating=entity.rating,
            title=entity.title,
            comment=entity.comment,
            quality_rating=entity.quality_rating,
            delivery_rating=entity.delivery_rating,
            service_rating=entity.service_rating,
            value_rating=entity.value_rating,
            is_verified=entity.is_verified,
            is_public=entity.is_public,
            supplier_response=entity.supplier_response,
            supplier_response_at=entity.supplier_response_at.strftime(
                "%d/%m/%Y %H:%M") if entity.supplier_response_at else None,
            helpful_count=entity.helpful_count,
            not_helpful_count=entity.not_helpful_count,
            created_at=entity.created_at.strftime("%d/%m/%Y %H:%M") if entity.created_at else None,
            updated_at=entity.updated_at.strftime("%d/%m/%Y %H:%M") if entity.updated_at else None
        )