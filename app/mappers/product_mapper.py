# app/mappers/product_mapper.py
from typing import List, Optional
from app.models.product_entity import ProductEntity
from app.schemas.product import ProductSchema
from app.schemas.product_image import ProductImageSchema


class ProductMapper:
    """Mapper pour convertir entre ProductEntity et ProductSchema"""

    @staticmethod
    def entity_to_schema(entity: ProductEntity) -> ProductSchema:
        """Convertit ProductEntity vers ProductSchema"""
        if not entity:
            return None

        # Gestion sécurisée des relations
        supplier_name = None
        supplier_email = None
        supplier_is_verified = False
        if entity.supplier_id and entity.supplier:
            # company_profile peut être None (supplier sans profil entreprise)
            if entity.supplier.company_profile:
                supplier_name = entity.supplier.company_profile.company_name
                supplier_is_verified = bool(entity.supplier.company_profile.is_verified)
            supplier_email = entity.supplier.email

        category_name = None
        category_slug = None
        if entity.category_id and entity.category:
            category_name = entity.category.name
            category_slug = entity.category.slug

        # NOUVEAU: Gérer les images
        product_images = []
        primary_image_url = None
        primary_thumbnail_url = None

        if entity.product_images:
            # Convertir les images
            product_images = [
                ProductImageSchema(
                    id=img.id,
                    product_id=img.product_id,
                    image_url=img.image_url,
                    thumbnail_url=img.thumbnail_url,
                    display_order=img.display_order,
                    is_primary=img.is_primary,
                    alt_text=img.alt_text,
                    file_name=img.file_name,
                    file_size=img.file_size,
                    width=img.width,
                    height=img.height,
                    # created_at=img.created_at.strftime("%d/%m/%Y %H:%M") if img.created_at else None
                    created_at=img.created_at
                )
                for img in entity.product_images
                if not img.is_deleted
            ]

            # Récupérer l'image principale
            primary_image = next((img for img in entity.product_images if img.is_primary and not img.is_deleted),
                                 None)
            if primary_image:
                primary_image_url = primary_image.image_url
                primary_thumbnail_url = primary_image.thumbnail_url
            elif product_images:  # Sinon prendre la première
                primary_image_url = product_images[0].image_url
                primary_thumbnail_url = product_images[0].thumbnail_url

            # NOUVEAU: Gérer les documents
            # product_documents = []
            # if entity.product_documents:
            #     product_documents = [
            #         ProductDocumentSchema(
            #             id=doc.id,
            #             product_id=doc.product_id,
            #             document_url=doc.document_url,
            #             document_type=doc.document_type,
            #             title=doc.title,
            #             description=doc.description,
            #             file_name=doc.file_name,
            #             file_size=doc.file_size,
            #             mime_type=doc.mime_type,
            #             created_at=doc.created_at.strftime("%d/%m/%Y %H:%M") if doc.created_at else None
            #         )
            #         for doc in entity.product_documents
            #         if not doc.is_deleted
            #     ]

        return ProductSchema(
            id=entity.id,
            supplier_id=entity.supplier_id,
            category_id=entity.category_id,
            name=entity.name,
            slug=entity.slug,
            description=entity.description,
            short_description=entity.short_description,
            sku=entity.sku,
            price=entity.price,
            original_price=entity.original_price,
            currency=entity.currency,
            min_order_quantity=entity.min_order_quantity,
            stock_quantity=entity.stock_quantity,
            unit=entity.unit,
            shipping_cost_override=entity.shipping_cost_override,
            # images=entity.images if entity.images else [],
            attributes=entity.attributes if entity.attributes else {},
            is_active=entity.is_active,
            is_featured=entity.is_featured,
            views_count=entity.views_count,
            # Agrégats d'avis (propriétés calculées sur l'entité)
            average_rating=entity.average_rating,
            reviews_count=entity.reviews_count,
            is_deleted=entity.is_deleted,
            # created_by=entity.created_by,
            # updated_by=entity.updated_by,
            created_at=entity.created_at.strftime("%d/%m/%Y %H:%M") if entity.created_at else None,
            updated_at=entity.updated_at.strftime("%d/%m/%Y %H:%M") if entity.updated_at else None,

            # Relations
            supplier_name=supplier_name,
            supplier_email=supplier_email,
            supplier_is_verified=supplier_is_verified,
            category_name=category_name,
            category_slug=category_slug,

            # Images et documents
            product_images=product_images,
            # product_documents=product_documents,
            primary_image_url=primary_image_url,
            primary_thumbnail_url=primary_thumbnail_url
        )

    @staticmethod
    def entities_to_schemas(entities: List[ProductEntity]) -> List[ProductSchema]:
        """Convertit une liste d'entités vers une liste de schémas"""
        if not entities:
            return []
        return [ProductMapper.entity_to_schema(entity) for entity in entities]

    @staticmethod
    def schema_to_entity(schema: ProductSchema) -> ProductEntity:
        """Convertit ProductSchema vers ProductEntity (pour création/update)"""
        entity = ProductEntity()

        if schema.id:
            entity.id = schema.id
        if schema.supplier_id:
            entity.supplier_id = schema.supplier_id
        if schema.category_id:
            entity.category_id = schema.category_id
        if schema.name:
            entity.name = schema.name
        if schema.slug:
            entity.slug = schema.slug
        if schema.description:
            entity.description = schema.description
        if schema.short_description:
            entity.short_description = schema.short_description
        if schema.sku:
            entity.sku = schema.sku
        if schema.price is not None:
            entity.price = schema.price
        if schema.currency:
            entity.currency = schema.currency
        if schema.min_order_quantity is not None:
            entity.min_order_quantity = schema.min_order_quantity
        if schema.stock_quantity is not None:
            entity.stock_quantity = schema.stock_quantity
        if schema.unit:
            entity.unit = schema.unit
        if schema.images is not None:
            entity.images = schema.images
        if schema.attributes is not None:
            entity.attributes = schema.attributes
        if schema.is_active is not None:
            entity.is_active = schema.is_active
        if schema.is_featured is not None:
            entity.is_featured = schema.is_featured
        if schema.views_count is not None:
            entity.views_count = schema.views_count
        if schema.is_deleted is not None:
            entity.is_deleted = schema.is_deleted
        # if schema.created_by:
        #     entity.created_by = schema.created_by
        # if schema.updated_by:
        #     entity.updated_by = schema.updated_by

        return entity