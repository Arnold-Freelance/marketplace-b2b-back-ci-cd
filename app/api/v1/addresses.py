"""
Routes carnet d'adresses (REST idiomatique).

- GET    /api/v1/addresses          mes adresses (celle par défaut en tête)
- POST   /api/v1/addresses          ajouter une adresse
- PUT    /api/v1/addresses/{id}     modifier (partiel)
- DELETE /api/v1/addresses/{id}     supprimer

Une seule adresse par défaut à la fois — garanti par le service, pas par le client.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.repositories.address_repo import AddressRepository
from app.schemas.address import AddressCreateSchema, AddressSchema, AddressUpdateSchema
from app.schemas.base import ResponseBase
from app.services.address_service import AddressService

router = APIRouter(prefix="/api/v1/addresses", tags=["Addresses"])


def get_address_service(db: Session = Depends(get_db)) -> AddressService:
    return AddressService(AddressRepository(db))


@router.get("", response_model=ResponseBase[AddressSchema])
async def list_my_addresses(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[AddressService, Depends(get_address_service)],
):
    """Mes adresses de livraison."""
    return service.list_mine(user_id)


@router.post("", response_model=ResponseBase[AddressSchema], status_code=status.HTTP_201_CREATED)
async def create_address(
    data: AddressCreateSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[AddressService, Depends(get_address_service)],
):
    """Ajouter une adresse. La première créée devient l'adresse par défaut."""
    return service.create(user_id, data)


@router.put("/{address_id}", response_model=ResponseBase[AddressSchema])
async def update_address(
    data: AddressUpdateSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[AddressService, Depends(get_address_service)],
    address_id: int = Path(..., gt=0),
):
    """Modifier une adresse (partiel — seuls les champs envoyés sont écrits)."""
    return service.update(user_id, address_id, data)


@router.delete("/{address_id}", response_model=ResponseBase[AddressSchema])
async def delete_address(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[AddressService, Depends(get_address_service)],
    address_id: int = Path(..., gt=0),
):
    """Supprimer une adresse. Si c'était celle par défaut, une autre la remplace."""
    return service.delete(user_id, address_id)
