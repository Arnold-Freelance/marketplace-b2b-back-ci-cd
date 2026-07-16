# app/services/category_service.py
from typing import Optional

from app.services.base_service import BaseService, ValidationHelper
from app.repositories.category_repo import CategoryRepo
from app.repositories.product_repo import ProductRepository
from app.models.category_entity import CategoryEntity
from app.schemas.category import CategorySchema
from app.schemas.base import RequestBase, ResponseBase
from app.mappers.category_mapper import CategoryMapper
from app.core.exceptions import ValidationError, BusinessRuleError
from app.core.logger import logger


class CategoryService(BaseService[CategoryEntity, CategorySchema]):
    """
    Service pour la gestion des catégories

    Hérite de BaseService qui fournit les opérations CRUD de base.
    On ne surcharge que les validations métier spécifiques.
    """

    def __init__(self, category_repo: CategoryRepo, product_repo: ProductRepository):
        super().__init__(category_repo, CategoryMapper)
        self.category_repo = category_repo  # Typage spécifique
        self.product_repo = product_repo

    # ==================== LECTURE PUBLIQUE (T2) ====================

    def get_by_criteria(
        self, request: RequestBase[CategorySchema]
    ) -> ResponseBase[CategorySchema]:
        """Lister les catégories selon critères — **public** (browsing catalogue).

        Surcharge de `BaseService.get_by_criteria` pour ne PAS exiger
        d'utilisateur : le listing des catégories est ouvert aux visiteurs
        anonymes. L'autorisation reste portée par la route (aucune pour la
        lecture, guard admin pour les écritures — cf. T6).
        """
        count = self.category_repo.count(request)
        if count == 0:
            return ResponseBase[CategorySchema](
                success=True,
                message="Aucune catégorie trouvée",
                items=[],
                total=0,
                limit=request.limit,
                offset=request.offset,
            )

        entities = self.category_repo.get_by_criteria(request)
        schemas = [
            self._enrich_schema(self.mapper.entity_to_schema(entity))
            for entity in entities
        ]
        return ResponseBase[CategorySchema](
            success=True,
            message="Catégories récupérées avec succès",
            items=schemas,
            total=count,
            limit=request.limit,
            offset=request.offset,
        )

    # ==================== VALIDATIONS MÉTIER SPÉCIFIQUES ====================

    def _validate_create_business_rules(self, request: RequestBase[CategorySchema]) -> None:
        """Validation métier pour la création d'une catégorie"""
        data = request.data

        # Validation du nom (2-100 caractères)
        ValidationHelper.validate_string_field(
            value=data.name,
            field_name="nom",
            min_length=2,
            max_length=100,
            required=True
        )

        # Validation du slug si fourni
        if data.slug:
            ValidationHelper.validate_string_field(
                value=data.slug,
                field_name="slug",
                max_length=255,
                required=False
            )

        # Vérifier l'unicité du nom
        ValidationHelper.validate_uniqueness(
            repository=self.category_repo,
            field_name="name",
            value=data.name
        )

        # Vérifier que le parent existe si spécifié
        if data.parent_id:
            ValidationHelper.validate_foreign_key(
                repository=self.category_repo,
                fk_id=data.parent_id,
                fk_name="parent"
            )

    def _validate_update_business_rules(
            self,
            request: RequestBase[CategorySchema],
            existing_entity: CategoryEntity
    ) -> None:
        """Validation métier pour la mise à jour"""
        data = request.data

        # Validation du nom si modifié
        if data.name:
            ValidationHelper.validate_string_field(
                value=data.name,
                field_name="nom",
                min_length=2,
                max_length=100,
                required=True
            )

            # Vérifier l'unicité (en excluant l'entité actuelle)
            if data.name != existing_entity.name:
                ValidationHelper.validate_uniqueness(
                    repository=self.category_repo,
                    field_name="name",
                    value=data.name,
                    exclude_id=existing_entity.id
                )

        # Validation du slug si modifié
        if data.slug:
            ValidationHelper.validate_string_field(
                value=data.slug,
                field_name="slug",
                max_length=255,
                required=False
            )

        # Vérifier la relation parent si modifiée
        if data.parent_id is not None:
            self._validate_parent_relationship(
                category_id=existing_entity.id,
                parent_id=data.parent_id
            )

    def _validate_delete_business_rules(
            self,
            entity_id: int,
            existing_entity: CategoryEntity
    ) -> None:
        """Validation métier pour la suppression"""
        # Vérifier qu'il n'y a pas de sous-catégories
        ValidationHelper.validate_no_children(
            repository=self.category_repo,
            parent_id=entity_id,
            relation_name="sous-catégories"
        )

        # Vérifier qu'il n'y a pas de produits associés
        ValidationHelper.validate_no_relations(
            repository=self.product_repo,
            entity_id=entity_id,
            method_name="get_by_category_id",
            relation_name="produits"
        )

    # ==================== MÉTHODES SPÉCIFIQUES AUX CATÉGORIES ====================

    def _validate_parent_relationship(self, category_id: int, parent_id: int) -> None:
        """
        Valider la relation parent-enfant

        Raises:
            BusinessRuleError: Si la relation est invalide
        """
        # Une catégorie ne peut pas être son propre parent
        if category_id == parent_id:
            raise BusinessRuleError("Une catégorie ne peut pas être son propre parent")

        # Vérifier que le parent existe
        ValidationHelper.validate_foreign_key(
            repository=self.category_repo,
            fk_id=parent_id,
            fk_name="parent"
        )

        # Optionnel: Vérifier les boucles circulaires
        if self._creates_circular_reference(category_id, parent_id):
            raise BusinessRuleError(
                "Cette relation créerait une référence circulaire dans la hiérarchie"
            )

    def _creates_circular_reference(self, category_id: int, parent_id: int) -> bool:
        """
        Vérifier si définir parent_id comme parent de category_id créerait une boucle

        Returns:
            True si boucle détectée
        """
        current_parent_id = parent_id
        visited = {category_id}

        while current_parent_id:
            if current_parent_id in visited:
                return True

            visited.add(current_parent_id)

            try:
                parent = self.category_repo.get_by_id(current_parent_id)
                current_parent_id = parent.parent_id
            except:
                break

        return False

    def _enrich_schema(self, schema: CategorySchema) -> CategorySchema:
        """
        Enrichir le schéma avec les enfants

        Args:
            schema: Schéma à enrichir

        Returns:
            Schéma enrichi avec les sous-catégories
        """
        if schema.id:
            schema.product_count = self.product_repo.count_by_category(schema.id)

        children = self.category_repo.get_by_parent_id(schema.id)
        if children:
            schema.children = CategoryMapper.entities_to_schemas(children)
        return schema

    # ==================== MÉTHODES SPÉCIFIQUES SUPPLÉMENTAIRES ====================

    def get_by_slug(self, slug: str) -> CategorySchema:
        """
        Récupérer une catégorie par son slug

        Args:
            slug: Slug de la catégorie

        Returns:
            Schéma de la catégorie

        Raises:
            NotFoundError: Si la catégorie n'existe pas
        """
        from app.core.exceptions import NotFoundError

        category = self.category_repo.get_by_slug(slug)
        if not category:
            raise NotFoundError("Category", f"slug={slug}")

        schema = CategoryMapper.entity_to_schema(category)
        return self._enrich_schema(schema)

    def get_hierarchy(self, parent_id: Optional[int] = None) -> list[CategorySchema]:
        """
        Récupérer la hiérarchie complète des catégories

        Args:
            parent_id: ID du parent (None pour racine)

        Returns:
            Liste des catégories avec leurs enfants
        """
        categories = self.category_repo.get_by_parent_id(parent_id) if parent_id else []

        schemas = []
        for category in categories:
            schema = CategoryMapper.entity_to_schema(category)
            # Récursion pour les enfants
            schema.children = self.get_hierarchy(category.id)
            schemas.append(schema)

        return schemas