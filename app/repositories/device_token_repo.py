# ================================================
# app/repositories/device_token_repo.py
# ================================================
"""
Repository pour les jetons push des appareils.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.enums import DevicePlatform, PushProvider
from app.models.messaging_entity import DeviceTokenEntity
from app.repositories.base import BaseRepository


class DeviceTokenRepository(BaseRepository):
    """Repository pour les jetons push."""

    def __init__(self, db: Session):
        super().__init__(db, DeviceTokenEntity)

    def upsert(
            self,
            user_id: int,
            token: str,
            platform: DevicePlatform,
            provider: PushProvider = PushProvider.EXPO,
            device_id: Optional[str] = None,
    ) -> DeviceTokenEntity:
        """Enregistre le jeton, ou le réassigne s'il existe déjà.

        Le `token` est unique globalement : si l'appareil a changé de compte, on
        déplace la ligne vers le nouvel utilisateur au lieu d'en créer une seconde.
        """
        existing = self.find_one_by(token=token)

        if existing:
            existing.user_id = user_id
            existing.platform = platform
            existing.provider = provider
            existing.device_id = device_id or existing.device_id
            existing.is_active = True
            existing.last_used_at = datetime.now()
            self.db.commit()
            self.db.refresh(existing)
            return existing

        # Une réinstallation produit un token neuf pour le même `device_id` :
        # on désactive l'ancien pour ne pas pousser dans le vide.
        if device_id:
            (
                self.db.query(DeviceTokenEntity)
                .filter(
                    DeviceTokenEntity.device_id == device_id,
                    DeviceTokenEntity.token != token,
                )
                .update({"is_active": False})
            )

        created = DeviceTokenEntity(
            user_id=user_id,
            token=token,
            platform=platform,
            provider=provider,
            device_id=device_id,
            is_active=True,
        )
        self.db.add(created)
        self.db.commit()
        self.db.refresh(created)
        return created

    def get_active_tokens(self, user_id: int) -> List[DeviceTokenEntity]:
        """Jetons actifs d'un utilisateur (cibles d'un push)."""
        return (
            self.db.query(DeviceTokenEntity)
            .filter(
                DeviceTokenEntity.user_id == user_id,
                DeviceTokenEntity.is_active.is_(True),
            )
            .all()
        )

    def deactivate(self, token: str, user_id: Optional[int] = None) -> bool:
        """Désactive un jeton (logout, ou `DeviceNotRegistered` côté relais).

        `user_id` restreint l'action au propriétaire : sans ce garde, un jeton
        divulgué permettrait à n'importe quel compte authentifié de couper les
        notifications d'un autre. Le dispatcher, lui, l'omet volontairement — il
        réagit au verdict du relais, pas à une requête utilisateur.
        """
        query = self.db.query(DeviceTokenEntity).filter(DeviceTokenEntity.token == token)
        if user_id is not None:
            query = query.filter(DeviceTokenEntity.user_id == user_id)

        updated = query.update({"is_active": False})
        self.db.commit()
        return updated > 0

    def purge_stale(self, older_than_days: int = 90) -> int:
        """Supprime les jetons inactifs et non utilisés depuis `older_than_days`."""
        cutoff = datetime.now() - timedelta(days=older_than_days)
        deleted = (
            self.db.query(DeviceTokenEntity)
            .filter(
                DeviceTokenEntity.is_active.is_(False),
                DeviceTokenEntity.last_used_at < cutoff,
            )
            .delete()
        )
        self.db.commit()
        return deleted
