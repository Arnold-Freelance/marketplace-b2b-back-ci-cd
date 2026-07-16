"""
Routes v2 commandes — pattern REST idiomatique.

- POST  /api/v1/orders                  créer une commande depuis le panier
- GET   /api/v1/orders                  mes commandes (role=buyer ou supplier)
- GET   /api/v1/orders/{id}             détail
- PUT   /api/v1/orders/{id}/status      changer le statut (fournisseur typiquement)
- POST  /api/v1/orders/{id}/cancel      annuler
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.repositories.address_repo import AddressRepository
from app.repositories.cart_repo import CartItemRepository, CartRepository
from app.repositories.company_profile_repo import CompanyProfileRepository
from app.repositories.device_token_repo import DeviceTokenRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.order_repo import (
    OrderItemRepository,
    OrderRepository,
    OrderStatusHistoryRepository,
)
from app.repositories.payment_repo import PaymentRepository
from app.repositories.product_repo import ProductRepository
from app.schemas.base import ResponseBase
from app.schemas.order import (
    CancelOrderSchema,
    CreateOrderSchema,
    OrderSchema,
    QuoteRequestSchema,
    QuoteSchema,
    UpdateOrderStatusSchema,
)
from app.services.notification_service import NotificationService
from app.services.order_service import OrderService
from app.services.push.dispatcher import PushDispatcher

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


def get_order_service(db: Session = Depends(get_db)) -> OrderService:
    return OrderService(
        OrderRepository(db),
        OrderItemRepository(db),
        OrderStatusHistoryRepository(db),
        CartRepository(db),
        CartItemRepository(db),
        ProductRepository(db),
        PaymentRepository(db),
        # Sans ce service, les commandes se créent mais personne n'est prévenu.
        notification_service=NotificationService(
            NotificationRepository(db),
            push_dispatcher=PushDispatcher(DeviceTokenRepository(db)),
        ),
        # Porte le barème de livraison du fournisseur.
        company_profile_repo=CompanyProfileRepository(db),
        # Permet de commander avec un simple `address_id` du carnet.
        address_repo=AddressRepository(db),
    )


@router.post("", response_model=ResponseBase[OrderSchema], status_code=status.HTTP_201_CREATED)
async def create_order_from_cart(
    data: CreateOrderSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[OrderService, Depends(get_order_service)],
):
    """
    Créer une (ou plusieurs) commande depuis le panier — une par fournisseur.
    Le panier est vidé après création.
    """
    return await service.create_order_from_cart(user_id, data)


@router.post("/quote", response_model=ResponseBase[QuoteSchema])
async def quote_cart(
    data: QuoteRequestSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[OrderService, Depends(get_order_service)],
):
    """Chiffrer le panier sans rien créer : ventilation par fournisseur, frais de
    livraison et total EXACTS de ce qui sera facturé à la validation.

    Déclarée avant `/{order_id}` : sinon FastAPI lirait « quote » comme un id.
    """
    return service.quote_cart(user_id, data.shipping_method)


@router.get("", response_model=ResponseBase[OrderSchema])
async def list_my_orders(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[OrderService, Depends(get_order_service)],
    role: Literal["buyer", "supplier"] = Query("buyer", description="Rôle pour filtrer"),
):
    """Liste mes commandes. `role=buyer` (envoyées) ou `role=supplier` (reçues)."""
    return service.get_my_orders(user_id, as_buyer=(role == "buyer"))


@router.get("/{order_id}", response_model=ResponseBase[OrderSchema])
async def get_order_details(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[OrderService, Depends(get_order_service)],
    order_id: int = Path(..., gt=0),
):
    """Détails d'une commande (accessible acheteur ou fournisseur)."""
    return service.get_order_by_id(order_id, user_id)


@router.put("/{order_id}/status", response_model=ResponseBase[OrderSchema])
async def update_order_status(
    data: UpdateOrderStatusSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[OrderService, Depends(get_order_service)],
    order_id: int = Path(..., gt=0),
):
    """Changer le statut d'une commande (transitions strictes)."""
    data.order_id = order_id
    return await service.update_order_status(user_id, data)


@router.post("/{order_id}/cancel", response_model=ResponseBase[OrderSchema])
async def cancel_order(
    data: CancelOrderSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[OrderService, Depends(get_order_service)],
    order_id: int = Path(..., gt=0),
):
    """Annuler une commande (remet le stock). Possible si pending/confirmed."""
    data.order_id = order_id
    return await service.cancel_order(user_id, data)
