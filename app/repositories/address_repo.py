# app/repositories/address_repo.py
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.address_entity import AddressEntity
from app.repositories.base import BaseRepository


class AddressRepository(BaseRepository):
    """Repository du carnet d'adresses."""

    def __init__(self, db: Session):
        super().__init__(db, AddressEntity)

    def get_by_user_id(self, user_id: int) -> List[AddressEntity]:
        """Adresses actives de l'utilisateur, celle par défaut en tête."""
        return (
            self.db.query(AddressEntity)
            .filter(
                AddressEntity.user_id == user_id,
                AddressEntity.is_deleted.is_(False),
            )
            .order_by(AddressEntity.is_default.desc(), AddressEntity.id.desc())
            .all()
        )

    def get_owned(self, address_id: int, user_id: int) -> Optional[AddressEntity]:
        """Une adresse, à condition qu'elle appartienne bien à l'utilisateur.

        Filtrer sur `user_id` ici plutôt que de vérifier après coup : on ne peut
        pas oublier le contrôle d'accès si la requête ne peut rien renvoyer d'autre.
        """
        return (
            self.db.query(AddressEntity)
            .filter(
                AddressEntity.id == address_id,
                AddressEntity.user_id == user_id,
                AddressEntity.is_deleted.is_(False),
            )
            .first()
        )

    def clear_default(self, user_id: int, except_id: Optional[int] = None) -> None:
        """Retire le drapeau « par défaut » de toutes les adresses de l'utilisateur.

        Appelé avant d'en promouvoir une autre : c'est ce qui garantit qu'il n'y
        a jamais deux adresses par défaut.
        """
        query = self.db.query(AddressEntity).filter(
            AddressEntity.user_id == user_id,
            AddressEntity.is_default.is_(True),
        )
        if except_id is not None:
            query = query.filter(AddressEntity.id != except_id)
        query.update({AddressEntity.is_default: False}, synchronize_session=False)

    def count_active(self, user_id: int) -> int:
        return (
            self.db.query(AddressEntity)
            .filter(
                AddressEntity.user_id == user_id,
                AddressEntity.is_deleted.is_(False),
            )
            .count()
        )
