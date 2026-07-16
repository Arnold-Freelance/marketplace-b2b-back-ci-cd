"""
PaymentService — orchestration des paiements de commandes.

Architecture : suit le pattern services/repositories du projet. Le PSP réel
est abstrait derrière `PaymentProvider` (cf. services/payment/provider.py).
Par défaut on utilise `MockMobileMoneyProvider` (scaffold) ; brancher un vrai
PSP = passer une autre implémentation au constructeur.

Workflow :
  initiate_payment  → crée un PaymentEntity PENDING + appelle provider.initiate
  handle_callback   → met à jour le statut paiement + le payment_status de
                      la commande (PAID si COMPLETED)
  get_order_payments → historique des paiements d'une commande
  refund_payment    → provider.refund + statut REFUNDED
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.logger import logger
from app.models.order_entity import PaymentMethod, PaymentStatus, OrderStatus
from app.repositories.order_repo import OrderRepository
from app.repositories.payment_repo import PaymentRepository
from app.schemas.base import ResponseBase
from app.schemas.payment import (
    InitiatePaymentSchema,
    PaymentCallbackSchema,
    PaymentSchema,
    RefundPaymentSchema,
)
from app.services.payment.provider import PaymentProvider, MockMobileMoneyProvider


class PaymentService:
    """Service de gestion des paiements."""

    def __init__(
        self,
        payment_repo: PaymentRepository,
        order_repo: OrderRepository,
        provider: Optional[PaymentProvider] = None,
    ):
        self.payment_repo = payment_repo
        self.order_repo = order_repo
        # Scaffold : provider mock par défaut. Injecter un vrai PSP en prod.
        self.provider = provider or MockMobileMoneyProvider()

    # ==================== INITIATION ====================

    def initiate_payment(
        self, user_id: int, data: InitiatePaymentSchema
    ) -> ResponseBase[PaymentSchema]:
        """Démarre un paiement pour une commande appartenant à l'utilisateur."""
        order = self.order_repo.get_by_id(data.order_id, raise_if_missing=False)
        if not order:
            raise NotFoundError("Commande", data.order_id)

        # Seul l'acheteur de la commande peut payer
        if order.buyer_id != user_id:
            raise BusinessRuleError("Vous n'êtes pas autorisé à payer cette commande")

        # Empêcher un double paiement
        existing = self.payment_repo.get_successful_payment(order.id)
        if existing:
            raise BusinessRuleError("Cette commande est déjà payée")

        # Appel PSP (mock par défaut)
        init = self.provider.initiate(
            amount=float(order.total_amount),
            currency=order.currency or "XOF",
            reference=order.order_number or f"ORDER-{order.id}",
            return_url=data.return_url,
            cancel_url=data.cancel_url,
            metadata={"order_id": order.id, "buyer_id": user_id},
        )

        # Créer l'enregistrement de paiement (PENDING)
        payment = self.payment_repo.create(
            order_id=order.id,
            payment_method=data.payment_method,
            payment_status=PaymentStatus.PENDING,
            amount=order.total_amount,
            currency=order.currency or "XOF",
            transaction_id=init.transaction_id,
            payment_provider=init.provider,
            payment_details=init.raw,
        )

        logger.info(
            f"Paiement initié — order={order.id} tx={init.transaction_id} "
            f"provider={init.provider}"
        )

        schema = PaymentSchema.model_validate(payment)
        # Exposer l'URL de paiement au client (champ hors entité)
        schema.payment_details = {
            **(schema.payment_details or {}),
            "payment_url": init.payment_url,
        }

        return ResponseBase[PaymentSchema](
            success=True,
            message="Paiement initié",
            item=schema,
        )

    # ==================== CALLBACK PSP ====================

    def handle_callback(self, data: PaymentCallbackSchema) -> ResponseBase[PaymentSchema]:
        """
        Traite le callback du PSP (webhook). Met à jour le paiement ET la
        commande. Public côté route (le PSP n'a pas de JWT) mais on s'appuie
        sur le transaction_id + une vérification provider.verify.
        """
        payment = self.payment_repo.get_by_transaction_id(data.transaction_id)
        if not payment:
            raise NotFoundError("Paiement", data.transaction_id)

        # Vérifier auprès du PSP (anti-spoofing du callback)
        verification = self.provider.verify(data.transaction_id)

        new_status = data.status
        if not verification.success:
            new_status = PaymentStatus.FAILED

        updates = {"payment_status": new_status}
        if new_status == PaymentStatus.COMPLETED:
            updates["paid_at"] = datetime.now(timezone.utc)
        elif new_status == PaymentStatus.FAILED:
            updates["failure_reason"] = verification.failure_reason or "Échec du paiement"

        if data.payment_details:
            updates["payment_details"] = {
                **(payment.payment_details or {}),
                **data.payment_details,
            }

        self.payment_repo.update(payment.id, **updates)

        # Répercuter sur la commande
        if new_status == PaymentStatus.COMPLETED:
            self.order_repo.update(
                payment.order_id,
                payment_status=PaymentStatus.COMPLETED,
                status=OrderStatus.PAID,
            )
            logger.info(f"Commande {payment.order_id} payée (tx={data.transaction_id})")

        payment = self.payment_repo.get_by_id(payment.id)
        return ResponseBase[PaymentSchema](
            success=True,
            message="Callback traité",
            item=PaymentSchema.model_validate(payment),
        )

    # ==================== CONSULTATION ====================

    def get_order_payments(
        self, user_id: int, order_id: int
    ) -> ResponseBase[PaymentSchema]:
        """Historique des paiements d'une commande (acheteur ou fournisseur)."""
        order = self.order_repo.get_by_id(order_id, raise_if_missing=False)
        if not order:
            raise NotFoundError("Commande", order_id)
        if user_id not in (order.buyer_id, order.supplier_id):
            raise BusinessRuleError("Accès non autorisé à cette commande")

        payments = self.payment_repo.get_by_order_id(order_id)
        items = [PaymentSchema.model_validate(p) for p in payments]
        return ResponseBase[PaymentSchema](
            success=True,
            message="Paiements récupérés",
            items=items,
            total=len(items),
        )

    # ==================== REMBOURSEMENT ====================

    def refund_payment(
        self, user_id: int, data: RefundPaymentSchema
    ) -> ResponseBase[PaymentSchema]:
        """Rembourse un paiement (réservé au fournisseur de la commande)."""
        payment = self.payment_repo.get_by_id(data.payment_id, raise_if_missing=False)
        if not payment:
            raise NotFoundError("Paiement", data.payment_id)

        order = self.order_repo.get_by_id(payment.order_id, raise_if_missing=False)
        if not order:
            raise NotFoundError("Commande", payment.order_id)
        if order.supplier_id != user_id:
            raise BusinessRuleError("Seul le fournisseur peut rembourser")

        if payment.payment_status != PaymentStatus.COMPLETED:
            raise BusinessRuleError("Seul un paiement complété peut être remboursé")

        refund_amount = float(data.amount) if data.amount else float(payment.amount)
        ok = self.provider.refund(payment.transaction_id, refund_amount)
        if not ok:
            raise BusinessRuleError("Le remboursement a échoué côté PSP")

        self.payment_repo.update(
            payment.id,
            payment_status=PaymentStatus.REFUNDED,
            refunded_at=datetime.now(timezone.utc),
            failure_reason=f"Remboursé: {data.reason}",
        )
        self.order_repo.update(
            order.id,
            payment_status=PaymentStatus.REFUNDED,
            status=OrderStatus.REFUNDED,
        )

        logger.info(f"Paiement {payment.id} remboursé ({refund_amount})")
        payment = self.payment_repo.get_by_id(payment.id)
        return ResponseBase[PaymentSchema](
            success=True,
            message="Remboursement effectué",
            item=PaymentSchema.model_validate(payment),
        )
