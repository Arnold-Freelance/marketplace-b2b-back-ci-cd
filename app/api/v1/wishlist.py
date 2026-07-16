"""
Routes v2 wishlist (favoris) — pattern REST idiomatique.

- POST   /api/v1/favorites                       ajouter
- DELETE /api/v1/favorites/{id}                  retirer
- PUT    /api/v1/favorites/{id}                  modifier (notes, priorité, notifs)
- GET    /api/v1/favorites                       ma wishlist
- GET    /api/v1/favorites/statistics            stats wishlist
- GET    /api/v1/favorites/by-product/{prod_id}  check si un produit est en favoris
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.repositories.favorite_repo import FavoriteRepository
from app.repositories.product_repo import ProductRepository
from app.schemas.base import ResponseBase
from app.schemas.favorite import (
    AddToFavoritesSchema,
    FavoriteSchema,
    FavoriteStatisticsSchema,
    UpdateFavoriteSchema,
)
from app.services.wishlist_service import WishlistService

router = APIRouter(prefix="/api/v1/favorites", tags=["Favorites"])


def get_wishlist_service(db: Session = Depends(get_db)) -> WishlistService:
    return WishlistService(FavoriteRepository(db), ProductRepository(db))


@router.post("", response_model=ResponseBase[FavoriteSchema], status_code=status.HTTP_201_CREATED)
async def add_favorite(
    data: AddToFavoritesSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[WishlistService, Depends(get_wishlist_service)],
):
    """Ajouter un produit aux favoris (1 fois max par produit, prix enregistré)."""
    return service.add_to_favorites(user_id, data)


@router.delete("/{favorite_id}", response_model=ResponseBase[FavoriteSchema])
async def remove_favorite(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[WishlistService, Depends(get_wishlist_service)],
    favorite_id: int = Path(..., gt=0),
):
    return service.remove_from_favorites(user_id, favorite_id)


@router.put("/{favorite_id}", response_model=ResponseBase[FavoriteSchema])
async def update_favorite(
    data: UpdateFavoriteSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[WishlistService, Depends(get_wishlist_service)],
    favorite_id: int = Path(..., gt=0),
):
    """Modifier notes / priorité / notifications d'un favori."""
    data.favorite_id = favorite_id
    return service.update_favorite(user_id, data)


@router.get("", response_model=ResponseBase[FavoriteSchema])
async def list_my_favorites(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[WishlistService, Depends(get_wishlist_service)],
):
    """Ma wishlist triée par priorité puis date (avec alertes baisse de prix)."""
    return service.get_my_favorites(user_id)


@router.get("/statistics", response_model=ResponseBase[FavoriteStatisticsSchema])
async def get_favorites_statistics(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[WishlistService, Depends(get_wishlist_service)],
):
    return service.get_favorites_statistics(user_id)


@router.get("/by-product/{product_id}")
async def check_is_favorite(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[WishlistService, Depends(get_wishlist_service)],
    product_id: int = Path(..., gt=0),
):
    """Vérifie si un produit est dans mes favoris (retourne {is_favorite: bool})."""
    return {"is_favorite": service.check_is_favorite(user_id, product_id)}
