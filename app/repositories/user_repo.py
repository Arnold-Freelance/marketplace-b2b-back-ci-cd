from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.repositories.base import BaseRepository
from app.models.user_entity import UserEntity
from app.models.user_role_entity import UserRoleEntity
from app.core.logger import logger


class UserRepository(BaseRepository):
    """Repository pour les requêtes utilisateurs - UNIQUEMENT requêtes BD"""

    def __init__(self, db: Session):
        super().__init__(db, UserEntity)

    def get_by_email(self, email: str) -> Optional[UserEntity]:
        """Récupérer un utilisateur par email"""
        try:
            return self.db.query(UserEntity).filter(
                UserEntity.email == email
            ).first()
        except Exception as e:
            logger.error(f"Erreur get_by_email: {str(e)}")
            return None

    def get_by_phone(self, phone: str) -> Optional[UserEntity]:
        """Récupérer un utilisateur par téléphone"""
        try:
            return self.db.query(UserEntity).filter(
                UserEntity.phone == phone
            ).first()
        except Exception as e:
            logger.error(f"Erreur get_by_phone: {str(e)}")
            return None

    def get_by_identifier(self, identifier: str) -> Optional[UserEntity]:
        """
        Récupérer un utilisateur par email OU téléphone
        Avec eager loading du profil entreprise
        """
        try:
            return self.db.query(UserEntity).options(
                joinedload(UserEntity.company_profile)
            ).filter(
                or_(
                    UserEntity.email == identifier,
                    UserEntity.phone == identifier
                )
            ).first()
        except Exception as e:
            logger.error(f"Erreur get_by_identifier: {str(e)}")
            return None

    def get_with_profile(self, user_id: int) -> Optional[UserEntity]:
        """Récupérer un utilisateur avec eager loading du profil"""
        try:
            return self.db.query(UserEntity).options(
                joinedload(UserEntity.company_profile)
            ).filter(UserEntity.id == user_id).first()
        except Exception as e:
            logger.error(f"Erreur get_with_profile: {str(e)}")
            return None

    # ==================== RÔLES (T5) ====================

    def get_roles(self, user_id: int) -> list[str]:
        """Liste des rôles d'un utilisateur, triée."""
        try:
            rows = (
                self.db.query(UserRoleEntity.role)
                .filter(UserRoleEntity.user_id == user_id)
                .all()
            )
            return sorted({r[0] for r in rows})
        except Exception as e:
            logger.error(f"Erreur get_roles: {str(e)}")
            return []

    def add_roles(self, user_id: int, roles: list[str]) -> None:
        """Ajouter des rôles à un utilisateur (idempotent, dédoublonné)."""
        try:
            existing = set(self.get_roles(user_id))
            for role in roles:
                if role in existing:
                    continue
                self.db.add(UserRoleEntity(user_id=user_id, role=role))
                existing.add(role)
            self.db.commit()
        except Exception as e:
            logger.error(f"Erreur add_roles: {str(e)}")
            self.db.rollback()
            raise

    def update_last_login(self, user_id: int) -> None:
        """Mettre à jour la date de dernière connexion"""
        try:
            from datetime import datetime
            self.db.query(UserEntity).filter(
                UserEntity.id == user_id
            ).update({"last_login": datetime.utcnow()})
            self.db.commit()
        except Exception as e:
            logger.error(f"Erreur update_last_login: {str(e)}")
            self.db.rollback()