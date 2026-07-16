"""
BaseRepository — accès SQL générique pour toutes les entités.

Phase 2 code-facto :
- Ajout du paramètre `autocommit` (défaut True pour compat ascendante).
- À TERME : passer autocommit=False et déléguer le commit au service
  (Unit of Work via @transactional). L'auto-commit par opération est un
  anti-pattern : si une étape métier échoue en milieu de service, les
  opérations précédentes sont déjà committées → incohérence.
- Helpers ajoutés : exists, count, find_by, find_one_by, list_paginated.
"""
from typing import Any, Dict, Optional, Type

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError


class BaseRepository:
    """
    Repository CRUD générique.

    Args:
        db: session SQLAlchemy
        entity_cls: classe de l'entité ORM
        autocommit: si True (legacy), chaque opération mutation commit
            immédiatement. Si False, c'est au service de gérer le commit
            (recommandé — voir helpers.transactional).
    """

    def __init__(self, db: Session, entity_cls: Type, autocommit: bool = True):
        self.db = db
        self.entity_cls = entity_cls
        self.autocommit = autocommit

    # ==================== LECTURES ====================

    def get_by_id(self, entity_id: int, raise_if_missing: bool = True):
        """Récupère par ID. Lève NotFoundError si absent (par défaut)."""
        obj = self.db.query(self.entity_cls).filter(self.entity_cls.id == entity_id).first()
        if not obj and raise_if_missing:
            raise NotFoundError(self.entity_cls.__name__, entity_id)
        return obj

    def find_one_by(self, **filters):
        """Premier résultat matchant les filtres, ou None."""
        return self.db.query(self.entity_cls).filter_by(**filters).first()

    def find_by(self, limit: int = 100, offset: int = 0, **filters):
        """Liste des entités matchant les filtres, paginée."""
        return (
            self.db.query(self.entity_cls)
            .filter_by(**filters)
            .limit(limit)
            .offset(offset)
            .all()
        )

    def exists(self, **filters) -> bool:
        """True si au moins une entité matche les filtres."""
        return (
            self.db.query(self.entity_cls.id).filter_by(**filters).first() is not None
        )

    def count(self, **filters) -> int:
        """Nombre d'entités matchant les filtres."""
        return self.db.query(func.count(self.entity_cls.id)).filter_by(**filters).scalar()

    # ==================== MUTATIONS ====================

    def create(self, **kwargs):
        obj = self.entity_cls(**kwargs)
        self.db.add(obj)
        if self.autocommit:
            self.db.commit()
            self.db.refresh(obj)
        else:
            self.db.flush()
            self.db.refresh(obj)
        return obj

    def update(self, entity_id: int, **kwargs):
        obj = self.get_by_id(entity_id)
        for k, v in kwargs.items():
            setattr(obj, k, v)
        if self.autocommit:
            self.db.commit()
            self.db.refresh(obj)
        else:
            self.db.flush()
            self.db.refresh(obj)
        return obj

    def delete(self, entity_id: int) -> bool:
        """Hard delete. Pour soft-delete, utiliser update(is_deleted=True)."""
        obj = self.get_by_id(entity_id)
        self.db.delete(obj)
        if self.autocommit:
            self.db.commit()
        else:
            self.db.flush()
        return True

    def soft_delete(self, entity_id: int) -> bool:
        """
        Soft-delete : marque is_deleted=True. L'entité doit avoir cette colonne.
        Lève AttributeError sinon (fail fast).
        """
        if not hasattr(self.entity_cls, "is_deleted"):
            raise AttributeError(
                f"{self.entity_cls.__name__} n'a pas de colonne is_deleted "
                "— soft_delete impossible, utiliser delete() ou ajouter la colonne."
            )
        self.update(entity_id, is_deleted=True)
        return True
