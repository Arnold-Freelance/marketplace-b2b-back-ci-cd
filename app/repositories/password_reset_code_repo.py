# app/repositories/password_reset_code_repo.py
"""Accès aux codes de réinitialisation."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.password_reset_code_entity import PasswordResetCodeEntity
from app.repositories.base import BaseRepository


class PasswordResetCodeRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, PasswordResetCodeEntity)

    def invalidate_all_for_user(self, user_id: int) -> None:
        """Désactiver les codes en cours d'un utilisateur.

        Appelé avant d'en émettre un nouveau : sans ça, chaque demande laisserait
        un code valide de plus en circulation, et redemander un code dix fois
        donnerait dix chances de tomber juste par force brute.
        """
        (
            self.db.query(PasswordResetCodeEntity)
            .filter(
                PasswordResetCodeEntity.user_id == user_id,
                PasswordResetCodeEntity.is_active.is_(True),
            )
            .update({"is_active": False}, synchronize_session=False)
        )
        self.db.commit()

    def get_active_for_user(self, user_id: int) -> Optional[PasswordResetCodeEntity]:
        """Le code actif et non expiré de l'utilisateur, s'il en a un.

        Filtre sur l'expiration en base plutôt que côté appelant : un code expiré
        ne doit jamais remonter, quelle que soit la façon dont on l'interroge.
        """
        return (
            self.db.query(PasswordResetCodeEntity)
            .filter(
                PasswordResetCodeEntity.user_id == user_id,
                PasswordResetCodeEntity.is_active.is_(True),
                PasswordResetCodeEntity.used_at.is_(None),
                PasswordResetCodeEntity.expires_at > datetime.now(timezone.utc),
            )
            .order_by(PasswordResetCodeEntity.id.desc())
            .first()
        )
