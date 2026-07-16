"""
Routes v2 panier — pattern REST idiomatique.

- GET    /api/v1/cart            mon panier
- POST   /api/v1/cart/items      ajouter un produit
- PUT    /api/v1/cart/items/{id} modifier la quantité d'un item
- DELETE /api/v1/cart/items/{id} retirer un item
- DELETE /api/v1/cart            vider le panier
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.repositories.cart_repo import CartItemRepository, CartRepository
from app.repositories.product_repo import ProductRepository
from app.schemas.base import ResponseBase
from app.schemas.cart import (
    AddToCartSchema,
    CartSchema,
    MergeCartSchema,
    UpdateCartItemSchema,
)
from app.services.cart_service import CartService

router = APIRouter(prefix="/api/v1/cart", tags=["Cart"])


def get_cart_service(db: Session = Depends(get_db)) -> CartService:
    return CartService(
        CartRepository(db),
        CartItemRepository(db),
        ProductRepository(db),
    )


@router.get("", response_model=ResponseBase[CartSchema])
async def get_my_cart(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[CartService, Depends(get_cart_service)],
):
    """Mon panier actif (créé à la volée si inexistant)."""
    return service.get_or_create_cart(user_id)


@router.post("/merge", response_model=ResponseBase[CartSchema])
async def merge_guest_cart(
    data: MergeCartSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[CartService, Depends(get_cart_service)],
):
    """Fusionne le panier invité (client) dans le panier serveur, à la connexion.

    Additionne les quantités par produit ; tolérant aux articles devenus
    indisponibles (ignorés / plafonnés au stock). À appeler juste après le login,
    puis vider le panier local côté client.
    """
    return service.merge_guest_cart(user_id, data.items)


@router.post("/items", response_model=ResponseBase[CartSchema], status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    data: AddToCartSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[CartService, Depends(get_cart_service)],
):
    """Ajouter un produit au panier (incrémente la quantité si déjà présent)."""
    return service.add_to_cart(user_id, data)


@router.put("/items/{cart_item_id}", response_model=ResponseBase[CartSchema])
async def update_cart_item(
    data: UpdateCartItemSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[CartService, Depends(get_cart_service)],
    cart_item_id: int = Path(..., gt=0),
):
    """Modifier la quantité d'un item (l'id du path écrase celui du body si présent)."""
    data.cart_item_id = cart_item_id
    return service.update_cart_item(user_id, data)


@router.delete("/items/{cart_item_id}", response_model=ResponseBase[CartSchema])
async def remove_cart_item(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[CartService, Depends(get_cart_service)],
    cart_item_id: int = Path(..., gt=0),
):
    return service.remove_from_cart(user_id, cart_item_id)


@router.delete("", response_model=ResponseBase[CartSchema])
async def clear_cart(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[CartService, Depends(get_cart_service)],
):
    """Vider tous les items du panier."""
    return service.clear_cart(user_id)
