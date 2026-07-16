# app/services/base_service.py
from typing import TypeVar, Generic, List, Optional, Type, Dict, Any
from abc import ABC, abstractmethod

from app.repositories.base import BaseRepository
from app.schemas.base import RequestBase, ResponseBase
from app.core.exceptions import ValidationError, NotFoundError, BusinessRuleError
from app.core.logger import logger, log_method_call

T = TypeVar('T')  # Type de l'entité
S = TypeVar('S')  # Type du schéma


class BaseService(ABC, Generic[T, S]):
    """
    Service de base générique pour les opérations CRUD

    Toutes les exceptions sont levées directement et seront gérées par le middleware
    """

    def __init__(self, repository: BaseRepository, mapper_class: Type):
        """
        Args:
            repository: Repository pour accéder aux données
            mapper_class: Classe de mapping Entity <-> Schema
        """
        self.repository = repository
        self.mapper = mapper_class
        self.entity_name = repository.entity_cls.__name__.replace('Entity', '')

    # ==================== MÉTHODES CRUD GÉNÉRIQUES ====================

    @log_method_call
    def create(self, request: RequestBase[S]) -> ResponseBase[S]:
        """
        Créer une nouvelle entité

        Args:
            request: Requête contenant les données

        Returns:
            Schéma de l'entité créée

        Raises:
            ValidationError: Si les données sont invalides
            BusinessRuleError: Si règle métier violée
        """
        # Validation
        self._validate_user(request)
        self._validate_data(request, is_update=False)
        self._validate_create_business_rules(request)

        # Préparation des données
        data = self._prepare_create_data(request)

        # Création
        entity = self.repository.create(**data)

        logger.info(f"{self.entity_name} créé(e) avec succès - ID: {entity.id}")

        # Conversion et retour

        return ResponseBase[S](
            success=True,
            message=f"Création réussie avec succès",
            item=self.mapper.entity_to_schema(entity)
        )

    @log_method_call
    def update(self, request: RequestBase[S]) -> ResponseBase[S]:
        """
        Mettre à jour une entité

        Args:
            request: Requête contenant les données de mise à jour

        Returns:
            Schéma de l'entité mise à jour

        Raises:
            ValidationError: Si les données sont invalides
            NotFoundError: Si l'entité n'existe pas
            BusinessRuleError: Si règle métier violée
        """
        # Validation
        self._validate_user(request)
        self._validate_data(request, is_update=True)
        entity_id = self._extract_entity_id(request)

        # Vérifier l'existence
        existing_entity = self.repository.get_by_id(entity_id)

        # Validation métier
        self._validate_update_business_rules(request, existing_entity)

        # Préparation des données
        update_data = self._prepare_update_data(request, existing_entity)

        # Mise à jour
        updated_entity = self.repository.update(entity_id, **update_data)

        logger.info(f"{self.entity_name} mis(e) à jour - ID: {entity_id}")
        return ResponseBase[S](
            success=True,
            message=f"Modification réussie avec succès",
            item=self.mapper.entity_to_schema(updated_entity)
        )

    @log_method_call
    def delete(self, request: RequestBase[S]) -> ResponseBase[S]:
        """
        Supprimer une entité (soft delete)

        Args:
            request: Requête contenant l'ID

        Returns:
            Message de confirmation

        Raises:
            ValidationError: Si les données sont invalides
            NotFoundError: Si l'entité n'existe pas
            BusinessRuleError: Si la suppression est impossible
        """
        # Validation
        self._validate_user(request)
        entity_id = self._extract_entity_id(request)

        # Vérifier l'existence
        existing_entity = self.repository.get_by_id(entity_id)

        # Validation métier
        self._validate_delete_business_rules(entity_id, existing_entity)

        # Soft delete
        self.repository.update(
            entity_id,
            is_deleted=True,
            updated_by=request.user
        )

        logger.info(f"{self.entity_name} supprimé(e) - ID: {entity_id}")

        return ResponseBase[S](
            success=True,
            message=f"{self.entity_name} supprimé(e) avec succès"
        )

    @log_method_call
    def get_by_id(self, entity_id: int) -> ResponseBase[S]:
        """
        Récupérer une entité par ID

        Args:
            entity_id: ID de l'entité

        Returns:
            Schéma de l'entité

        Raises:
            NotFoundError: Si l'entité n'existe pas
        """
        entity = self.repository.get_by_id(entity_id)
        schema = self.mapper.entity_to_schema(entity)

        # Enrichissement si nécessaire

        return ResponseBase[S](
            success=True,
            message=f"Récuperation réussie avec succès",
            item=self._enrich_schema(schema)
        )

    @log_method_call
    def get_by_criteria(self, request: RequestBase[S]) -> ResponseBase[S]:
        """
        Récupérer les entités selon critères avec pagination

        Args:
            request: Requête avec critères

        Returns:
            ResponseBase avec liste paginée
        """
        self._validate_user(request)
        self._validate_data(request, is_update=False)
        # Comptage
        count = self.repository.count(request)

        if count == 0:
            return ResponseBase[S](
                success=True,
                message=f"Aucun(e) {self.entity_name} trouvé(e)",
                items=[],
                total=0,
                limit=request.limit,
                offset=request.offset
            )

        # Récupération
        entities = self.repository.get_by_criteria(request)

        # Conversion et enrichissement
        schemas = [
            self._enrich_schema(self.mapper.entity_to_schema(entity))
            for entity in entities
        ]

        return ResponseBase[S](
            success=True,
            message=f"{self.entity_name}s récupéré(e)s avec succès",
            items=schemas,
            total=count,
            limit=request.limit,
            offset=request.offset
        )

    # ==================== MÉTHODES DE VALIDATION (À SURCHARGER) ====================

    def _validate_user(self, request: RequestBase[S]) -> None:
        """Valider que l'utilisateur est présent"""
        if not request.user:
            raise ValidationError("L'ID utilisateur est obligatoire")

    def _validate_data(self, request: RequestBase[S], is_update: bool = False) -> None:
        """
        Valider les données de base

        Args:
            request: Requête à valider
            is_update: True si c'est une mise à jour
        """
        if not request.data:
            raise ValidationError("Les données sont obligatoires")

    def _extract_entity_id(self, request: RequestBase[S]) -> int:
        """Extraire l'ID de l'entité depuis la requête"""
        if not hasattr(request.data, 'id') or not request.data.id:
            raise ValidationError(f"L'ID du/de la {self.entity_name} est obligatoire")
        return request.data.id

    @abstractmethod
    def _validate_create_business_rules(self, request: RequestBase[S]) -> None:
        """
        Valider les règles métier pour la création
        À implémenter dans les classes filles
        """
        pass

    @abstractmethod
    def _validate_update_business_rules(self, request: RequestBase[S], existing_entity: T) -> None:
        """
        Valider les règles métier pour la mise à jour
        À implémenter dans les classes filles
        """
        pass

    @abstractmethod
    def _validate_delete_business_rules(self, entity_id: int, existing_entity: T) -> None:
        """
        Valider les règles métier pour la suppression
        À implémenter dans les classes filles
        """
        pass

    # ==================== MÉTHODES DE PRÉPARATION (À SURCHARGER SI BESOIN) ====================

    def _prepare_create_data(self, request: RequestBase[S]) -> Dict[str, Any]:
        """Préparer les données pour la création"""
        data = request.data.model_dump(exclude_none=True)
        data['created_by'] = request.user
        data['is_deleted'] = False
        return data

    def _prepare_update_data(self, request: RequestBase[S], existing_entity: T) -> Dict[str, Any]:
        """Préparer les données pour la mise à jour"""
        update_data = request.data.model_dump(exclude_none=True, exclude={'id'})
        update_data['updated_by'] = request.user
        return update_data

    def _enrich_schema(self, schema: S) -> S:
        """
        Enrichir le schéma avec des données supplémentaires
        À surcharger si nécessaire
        """
        return schema


# ==================== VALIDATEURS RÉUTILISABLES ====================

class ValidationHelper:
    """Classe utilitaire pour validations communes"""

    @staticmethod
    def validate_string_field(
            value: Optional[str],
            field_name: str,
            min_length: int = 0,
            max_length: int = None,
            required: bool = True
    ) -> None:
        """Valider un champ texte"""
        if required and (not value or not value.strip()):
            raise ValidationError(f"Le champ '{field_name}' est obligatoire")

        if value:
            length = len(value.strip())
            if length < min_length:
                raise ValidationError(
                    f"Le champ '{field_name}' doit contenir au moins {min_length} caractères"
                )
            if max_length and length > max_length:
                raise ValidationError(
                    f"Le champ '{field_name}' ne peut pas dépasser {max_length} caractères"
                )

    @staticmethod
    def validate_uniqueness(
            repository: BaseRepository,
            field_name: str,
            value: Any,
            exclude_id: Optional[int] = None
    ) -> None:
        """Vérifier l'unicité d'un champ"""
        method_name = f"get_by_{field_name}"
        if hasattr(repository, method_name):
            existing = getattr(repository, method_name)(value)
            if existing and (exclude_id is None or existing.id != exclude_id):
                raise BusinessRuleError(
                    f"Une entrée avec ce {field_name} '{value}' existe déjà"
                )

    @staticmethod
    def validate_foreign_key(
            repository: BaseRepository,
            fk_id: Optional[int],
            fk_name: str
    ) -> None:
        """Valider qu'une clé étrangère existe"""
        if fk_id is not None:
            try:
                repository.get_by_id(fk_id)
            except NotFoundError:
                raise ValidationError(f"Le {fk_name} avec l'ID {fk_id} n'existe pas")

    @staticmethod
    def validate_no_children(
            repository: BaseRepository,
            parent_id: int,
            relation_name: str = "enfants"
    ) -> None:
        """Vérifier qu'une entité n'a pas d'enfants"""
        method_name = "get_by_parent_id"
        if hasattr(repository, method_name):
            children = getattr(repository, method_name)(parent_id)
            if children:
                raise BusinessRuleError(
                    f"Impossible de supprimer: cette entrée a des {relation_name}"
                )

    @staticmethod
    def validate_no_relations(
            repository: BaseRepository,
            entity_id: int,
            method_name: str,
            relation_name: str
    ) -> None:
        """Vérifier qu'une entité n'a pas de relations"""
        if hasattr(repository, method_name):
            relations = getattr(repository, method_name)(entity_id)
            if relations:
                raise BusinessRuleError(
                    f"Impossible de supprimer: cette entrée est associée à des {relation_name}"
                )