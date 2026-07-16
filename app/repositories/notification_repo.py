# ================================================
# app/repositories/notification_repo.py
# ================================================
"""
Repository pour les notifications
"""
from typing import List, Optional, Sequence
from sqlalchemy.orm import Session
from app.core.enums import NotificationType
from app.models.messaging_entity import NotificationEntity
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    """Repository pour les notifications"""

    def __init__(self, db: Session):
        super().__init__(db, NotificationEntity)

    def get_user_notifications(
            self,
            user_id: int,
            unread_only: bool = False,
            limit: int = 50,
            offset: int = 0
    ) -> List[NotificationEntity]:
        """Récupérer les notifications d'un utilisateur"""
        query = self.db.query(NotificationEntity).filter(
            NotificationEntity.user_id == user_id
        )

        if unread_only:
            query = query.filter(NotificationEntity.is_read == False)

        return (
            query
            .order_by(NotificationEntity.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def find_by_event_key(self, user_id: int, event_key: str) -> Optional[NotificationEntity]:
        """Retrouve la notification déjà émise pour cet évènement (idempotence).

        Lookup indexé sur `(user_id, event_key)`. La contrainte d'unicité qui
        couvre ces colonnes reste le vrai garde-fou : ce `find` évite l'aller-retour
        d'une IntegrityError dans le cas nominal, il ne le remplace pas.
        """
        return self.find_one_by(user_id=user_id, event_key=event_key)

    def count_unread(self, user_id: int) -> int:
        """Compter les notifications non lues"""
        return (
            self.db.query(NotificationEntity)
            .filter(
                NotificationEntity.user_id == user_id,
                NotificationEntity.is_read == False
            )
            .count()
        )

    def count_unread_by_types(self, user_id: int, types: Sequence[NotificationType]) -> int:
        """Non-lues dont le type est dans `types` (badge « Commandes »)."""
        return (
            self.db.query(NotificationEntity)
            .filter(
                NotificationEntity.user_id == user_id,
                NotificationEntity.is_read == False,
                NotificationEntity.type.in_(tuple(types)),
            )
            .count()
        )

    def count_unread_excluding_types(self, user_id: int, types: Sequence[NotificationType]) -> int:
        """Non-lues dont le type n'est PAS dans `types` (badge cloche).

        Sert à exclure `new_message`, qui a déjà son propre compteur sur l'onglet
        Messages — l'inclure ferait compter deux fois le même événement.
        """
        return (
            self.db.query(NotificationEntity)
            .filter(
                NotificationEntity.user_id == user_id,
                NotificationEntity.is_read == False,
                NotificationEntity.type.notin_(tuple(types)),
            )
            .count()
        )

    def mark_all_as_read(self, user_id: int, types: Optional[Sequence[NotificationType]] = None) -> int:
        """Marquer les notifications comme lues.

        `types` restreint l'action à une catégorie (ex. ouvrir l'onglet Commandes ne
        doit pas vider la cloche).
        """
        from datetime import datetime

        query = self.db.query(NotificationEntity).filter(
            NotificationEntity.user_id == user_id,
            NotificationEntity.is_read == False
        )

        if types:
            query = query.filter(NotificationEntity.type.in_(tuple(types)))

        result = query.update(
            {"is_read": True, "read_at": datetime.now()},
            synchronize_session=False,
        )

        self.db.commit()
        return result