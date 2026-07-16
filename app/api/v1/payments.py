"""
Routes paiement (REST idiomatique).

- POST /api/v1/payments/initiate         démarrer un paiement de commande
- POST /api/v1/payments/callback         webhook PSP (public)
- GET  /api/v1/payments/order/{order_id} paiements d'une commande
- POST /api/v1/payments/refund           rembourser (fournisseur)

NB : le module utilise un provider mock (MockMobileMoneyProvider) tant qu'un
vrai PSP (CinetPay / Wave / Orange Money…) n'est pas branché. Voir
app/services/payment/provider.py.

Le callback est public (le PSP n'envoie pas de JWT) — il est whitelisté dans
AuthMiddleware. La sécurité repose sur la vérification provider.verify() +
le transaction_id. En prod, ajouter la vérification de signature du webhook.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.repositories.order_repo import OrderRepository
from app.repositories.payment_repo import PaymentRepository
from app.schemas.base import ResponseBase
from app.schemas.payment import (
    InitiatePaymentSchema,
    PaymentCallbackSchema,
    PaymentSchema,
    RefundPaymentSchema,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


def get_payment_service(db: Session = Depends(get_db)) -> PaymentService:
    return PaymentService(PaymentRepository(db), OrderRepository(db))


@router.post(
    "/initiate",
    response_model=ResponseBase[PaymentSchema],
    status_code=status.HTTP_201_CREATED,
)
async def initiate_payment(
    data: InitiatePaymentSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    """Démarre un paiement. Retourne transaction_id + payment_url (dans payment_details)."""
    return service.initiate_payment(user_id, data)


@router.post("/callback", response_model=ResponseBase[PaymentSchema])
async def payment_callback(
    data: PaymentCallbackSchema,
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    """Webhook PSP — met à jour le statut du paiement et de la commande. Public."""
    return service.handle_callback(data)


@router.get("/order/{order_id}", response_model=ResponseBase[PaymentSchema])
async def get_order_payments(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[PaymentService, Depends(get_payment_service)],
    order_id: int = Path(..., gt=0),
):
    """Historique des paiements d'une commande (acheteur ou fournisseur)."""
    return service.get_order_payments(user_id, order_id)


@router.post("/refund", response_model=ResponseBase[PaymentSchema])
async def refund_payment(
    data: RefundPaymentSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[PaymentService, Depends(get_payment_service)],
):
    """Rembourse un paiement complété (réservé au fournisseur)."""
    return service.refund_payment(user_id, data)
