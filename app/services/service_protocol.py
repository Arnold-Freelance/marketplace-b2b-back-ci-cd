"""
Contrats Protocol pour les nouveaux services métier (Phase 2 code-facto).

Inspiré de `IBasicBusiness<T, K>` du projet Spring Boot bbg-bes-configs,
adapté à Python avec `Protocol` (duck typing — pas d'héritage forcé).

Ce fichier coexiste avec l'ancien `base_service.BaseService` (classe
abstraite). Les nouveaux services peuvent simplement se conformer au
Protocol sans hériter de quoi que ce soit ; mypy/IDE vérifient la
conformité statiquement.

Convention :
- `user_id` est TOUJOURS un paramètre séparé, jamais dans le data/criteria
- L'identité vient du JWT via AuthMiddleware, pas du body
- Toutes les méthodes retournent un ResponseBase[R] (sauf count qui
  retourne un int)
"""
from typing import Generic, Optional, Protocol, TypeVar

from app.schemas.base import ResponseBase

T = TypeVar("T")  # schema d'entrée (DTO request)
R = TypeVar("R")  # schema de sortie (DTO response)


class BasicService(Protocol, Generic[T, R]):
    """Contrat minimal pour un service CRUD métier."""

    def create(self, data: T, user_id: int) -> ResponseBase[R]: ...

    def update(self, entity_id: int, data: T, user_id: int) -> ResponseBase[R]: ...

    def delete(self, entity_id: int, user_id: int) -> ResponseBase[R]: ...

    def get_by_id(self, entity_id: int) -> ResponseBase[R]: ...

    def get_by_criteria(
        self,
        criteria: Optional[T] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ResponseBase[R]: ...

    def count_by_criteria(self, criteria: Optional[T] = None) -> int: ...


class SoftDeletableService(BasicService[T, R], Protocol):
    """Extension pour les entités avec soft-delete : ajoute restore()."""

    def restore(self, entity_id: int, user_id: int) -> ResponseBase[R]: ...
