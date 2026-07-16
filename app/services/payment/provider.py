"""
Abstraction d'un prestataire de paiement (PSP).

L'interface `PaymentProvider` isole le code métier de l'implémentation
concrète d'un PSP (CinetPay, Wave, Orange Money, Stripe…). On peut ainsi
brancher un vrai PSP plus tard sans toucher au PaymentService.

`MockMobileMoneyProvider` simule un PSP Mobile Money pour le développement :
- `initiate` retourne un transaction_id + une URL de paiement simulée
- `verify` simule une transaction réussie
- `refund` simule un remboursement réussi

Pour brancher un vrai PSP : implémenter `PaymentProvider` avec les appels
HTTP réels et l'injecter dans PaymentService à la place du mock.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class PaymentInitResult:
    """Résultat d'une initiation de paiement côté PSP."""
    transaction_id: str
    payment_url: Optional[str] = None
    provider: str = "mock"
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentVerifyResult:
    """Résultat de la vérification d'une transaction côté PSP."""
    success: bool
    transaction_id: str
    raw: Dict[str, Any] = field(default_factory=dict)
    failure_reason: Optional[str] = None


class PaymentProvider(ABC):
    """Contrat d'un prestataire de paiement."""

    name: str = "abstract"

    @abstractmethod
    def initiate(
        self,
        amount: float,
        currency: str,
        reference: str,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentInitResult:
        """Démarre une transaction et retourne de quoi rediriger l'utilisateur."""

    @abstractmethod
    def verify(self, transaction_id: str) -> PaymentVerifyResult:
        """Vérifie l'état d'une transaction auprès du PSP."""

    @abstractmethod
    def refund(self, transaction_id: str, amount: Optional[float] = None) -> bool:
        """Rembourse (totalement ou partiellement) une transaction."""


class MockMobileMoneyProvider(PaymentProvider):
    """
    PSP factice simulant un flux Mobile Money.

    Aucune connexion réseau : tout réussit par défaut. Sert à développer et
    tester le workflow de paiement de bout en bout sans credentials réels.
    """

    name = "mock_mobile_money"

    def initiate(
        self,
        amount: float,
        currency: str,
        reference: str,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentInitResult:
        transaction_id = f"MOCK-{uuid.uuid4().hex[:16].upper()}"
        # URL simulée : en prod ce serait la page de paiement du PSP
        payment_url = f"https://sandbox.mock-psp.local/pay/{transaction_id}"
        return PaymentInitResult(
            transaction_id=transaction_id,
            payment_url=payment_url,
            provider=self.name,
            raw={
                "amount": amount,
                "currency": currency,
                "reference": reference,
                "return_url": return_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {},
            },
        )

    def verify(self, transaction_id: str) -> PaymentVerifyResult:
        # Mock : toute transaction connue est considérée réussie
        return PaymentVerifyResult(
            success=True,
            transaction_id=transaction_id,
            raw={"simulated": True},
        )

    def refund(self, transaction_id: str, amount: Optional[float] = None) -> bool:
        # Mock : remboursement toujours accepté
        return True
