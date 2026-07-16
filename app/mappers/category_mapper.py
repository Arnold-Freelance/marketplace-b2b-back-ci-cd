from typing import List

from app.models.category_entity import CategoryEntity
from app.schemas.category import CategorySchema


class CategoryMapper:
    @staticmethod
    def entity_to_schema(entity: CategoryEntity) -> CategorySchema:
        """Convertit CategoryEntity vers CategorySchema"""
        if not entity:
            return None

        # Gestion sécurisée de la relation parent
        parent_name = None
        parent_slug = None
        if entity.parent_id and entity.parent:
            parent_name = entity.parent.name
            parent_slug = entity.parent.slug

        return CategorySchema(
            id=entity.id,
            name=entity.name,
            slug=entity.slug,
            parent_id=entity.parent_id,
            description=entity.description,
            icon_url=entity.icon_url,
            is_active=entity.is_active,
            is_deleted=entity.is_deleted,
            created_by=entity.created_by,
            updated_by=entity.updated_by,
            created_at=entity.created_at.strftime("%d/%m/%Y") if entity.created_at else None,
            updated_at=entity.updated_at.strftime("%d/%m/%Y") if entity.updated_at else None,

            parent_name=parent_name,
            parent_slug=parent_slug,
        )

    @staticmethod
    def entities_to_schemas(entities: List[CategoryEntity]) -> List[CategorySchema]:
        """Convertit une liste d'entités vers une liste de schémas"""
        if not entities:
            return []
        return [CategoryMapper.entity_to_schema(entity) for entity in entities]

    @staticmethod
    def schema_to_entity(schema: CategorySchema) -> CategoryEntity:
        """Convertit CategorySchema vers CategoryEntity (pour création/update)"""
        entity = CategoryEntity()

        if schema.id:
            entity.id = schema.id
        if schema.name:
            entity.name = schema.name
        if schema.slug:
            entity.slug = schema.slug
        if schema.parent_id is not None:
            entity.parent_id = schema.parent_id
        if schema.description:
            entity.description = schema.description
        if schema.icon_url:
            entity.icon_url = schema.icon_url
        if schema.is_active is not None:
            entity.is_active = schema.is_active
        if schema.is_deleted is not None:
            entity.is_deleted = schema.is_deleted
        if schema.created_by:
            entity.created_by = schema.created_by
        if schema.updated_by:
            entity.updated_by = schema.updated_by

        return entity
