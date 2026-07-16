# app/services/address_service.py
"""Carnet d'adresses de livraison."""
from app.core.exceptions import NotFoundError
from app.core.logger import logger
from app.repositories.address_repo import AddressRepository
from app.schemas.address import AddressCreateSchema, AddressSchema, AddressUpdateSchema
from app.schemas.base import ResponseBase


class AddressService:
    """CRUD du carnet d'adresses. Une seule adresse par défaut, toujours."""

    def __init__(self, address_repo: AddressRepository):
        self.address_repo = address_repo

    def list_mine(self, user_id: int) -> ResponseBase[AddressSchema]:
        addresses = self.address_repo.get_by_user_id(user_id)
        items = [AddressSchema.model_validate(a) for a in addresses]
        return ResponseBase[AddressSchema](
            success=True,
            message="Adresses récupérées",
            items=items,
            total=len(items),
        )

    def create(self, user_id: int, data: AddressCreateSchema) -> ResponseBase[AddressSchema]:
        # La toute première adresse est forcément celle par défaut : sans ça,
        # l'acheteur aurait un carnet sans adresse pré-sélectionnée au paiement.
        is_first = self.address_repo.count_active(user_id) == 0
        make_default = data.is_default or is_first

        if make_default:
            self.address_repo.clear_default(user_id)

        address = self.address_repo.create(
            user_id=user_id,
            **{**data.model_dump(), "is_default": make_default},
        )
        logger.info(f"Adresse {address.id} créée pour user {user_id}")

        return ResponseBase[AddressSchema](
            success=True,
            message="Adresse ajoutée",
            item=AddressSchema.model_validate(address),
        )

    def update(self, user_id: int, address_id: int, data: AddressUpdateSchema) -> ResponseBase[AddressSchema]:
        address = self.address_repo.get_owned(address_id, user_id)
        if not address:
            raise NotFoundError("Adresse", address_id)

        # `exclude_unset` : une mise à jour partielle ne doit pas réécrire les
        # champs absents du corps avec leurs valeurs par défaut.
        changes = data.model_dump(exclude_unset=True)

        if changes.get("is_default"):
            self.address_repo.clear_default(user_id, except_id=address_id)
        elif changes.get("is_default") is False and address.is_default:
            # Refuser de laisser l'acheteur sans adresse par défaut : décocher la
            # seule adresse par défaut n'a pas de sens, on ignore le retrait.
            changes.pop("is_default")

        updated = self.address_repo.update(address_id, **changes)

        return ResponseBase[AddressSchema](
            success=True,
            message="Adresse mise à jour",
            item=AddressSchema.model_validate(updated),
        )

    def delete(self, user_id: int, address_id: int) -> ResponseBase[AddressSchema]:
        address = self.address_repo.get_owned(address_id, user_id)
        if not address:
            raise NotFoundError("Adresse", address_id)

        was_default = address.is_default
        # Suppression logique : les commandes passées figent déjà leur adresse en
        # JSON, mais on garde la ligne pour ne pas casser d'éventuelles reprises.
        self.address_repo.update(address_id, is_deleted=True, is_default=False)

        # L'acheteur ne doit jamais se retrouver sans adresse par défaut.
        if was_default:
            remaining = self.address_repo.get_by_user_id(user_id)
            if remaining:
                self.address_repo.update(remaining[0].id, is_default=True)

        logger.info(f"Adresse {address_id} supprimée pour user {user_id}")
        return ResponseBase[AddressSchema](success=True, message="Adresse supprimée")
