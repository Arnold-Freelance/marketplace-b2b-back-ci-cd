# ================================================
# app/schemas/payment.py
# ================================================
"""
Schémas pour les paiements
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.order_entity import OrderStatus, PaymentStatus, PaymentMethod, ShippingMethod
from app.schemas.schema_base import SchemaBase


class PaymentSchema(SchemaBase):
    """Schéma pour un paiement"""
    id: Optional[int] = None
    order_id: Optional[int] = None
    payment_method: PaymentMethod
    payment_status: PaymentStatus = PaymentStatus.PENDING
    amount: Decimal = Field(..., gt=0)
    currency: str = "XOF"
    transaction_id: Optional[str] = None
    payment_provider: Optional[str] = None
    payment_details: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None
    paid_at: Optional[str] = None
    refunded_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class InitiatePaymentSchema(BaseModel):
    """Schéma pour initier un paiement"""
    order_id: int = Field(..., gt=0)
    payment_method: PaymentMethod
    return_url: Optional[str] = None  # URL de retour après paiement
    cancel_url: Optional[str] = None  # URL d'annulation


class PaymentCallbackSchema(BaseModel):
    """Schéma pour le callback de paiement"""
    transaction_id: str
    status: PaymentStatus
    payment_details: Optional[Dict[str, Any]] = None


class RefundPaymentSchema(BaseModel):
    """Schéma pour rembourser un paiement"""
    payment_id: int = Field(..., gt=0)
    amount: Optional[Decimal] = None  # Si None, remboursement complet
    reason: str = Field(..., min_length=10, max_length=500)
