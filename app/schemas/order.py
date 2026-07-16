# ================================================
# app/schemas/order.py
# ================================================
"""
Schémas pour les commandes
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.order_entity import OrderStatus, PaymentStatus, PaymentMethod, ShippingMethod
from app.schemas.schema_base import SchemaBase


class OrderItemSchema(SchemaBase):
    """Schéma pour un item de commande"""
    id: Optional[int] = None
    order_id: Optional[int] = None
    product_id: Optional[int] = None
    product_name: str
    product_sku: Optional[str] = None
    product_image_url: Optional[str] = None
    quantity: int = Field(..., ge=1)
    unit_price: Decimal = Field(..., gt=0)
    subtotal: Decimal
    currency: str = "XOF"
    product_attributes: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class ShippingAddressSchema(BaseModel):
    """Schéma pour l'adresse de livraison"""
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=8, max_length=20)
    address_line1: str = Field(..., min_length=5, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: str = Field(default="Côte d'Ivoire", max_length=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Jean Kouassi",
                "phone": "+225 07 12 34 56 78",
                "address_line1": "Cocody Angré 8ème Tranche",
                "address_line2": "Près de la pharmacie",
                "city": "Abidjan",
                "state": "Abidjan",
                "postal_code": "00225",
                "country": "Côte d'Ivoire"
            }
        }
    )


class OrderStatusHistorySchema(BaseModel):
    """Une étape du suivi de commande.

    Alimente le fil « Suivi de livraison » de l'app : la table existait depuis le
    début et était bien écrite à chaque transition, mais n'était exposée nulle
    part — l'écran affichait donc un suivi vide.
    """
    id: int
    old_status: Optional[OrderStatus] = None
    new_status: OrderStatus
    comment: Optional[str] = None
    created_at: Optional[str] = None


class OrderSchema(SchemaBase):
    """Schéma pour une commande"""
    id: Optional[int] = None
    order_number: Optional[str] = None

    # Acteurs
    buyer_id: Optional[int] = None
    supplier_id: Optional[int] = None
    buyer_name: Optional[str] = None
    buyer_email: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_email: Optional[str] = None

    # Montants
    subtotal: Optional[Decimal] = None
    shipping_cost: Optional[Decimal] = Decimal("0.00")
    tax_amount: Optional[Decimal] = Decimal("0.00")
    discount_amount: Optional[Decimal] = Decimal("0.00")
    total_amount: Optional[Decimal] = None
    currency: str = "XOF"

    # Statuts
    status: Optional[OrderStatus] = OrderStatus.PENDING
    payment_status: Optional[PaymentStatus] = PaymentStatus.PENDING

    # Livraison
    shipping_method: Optional[ShippingMethod] = ShippingMethod.STANDARD
    shipping_address: Optional[ShippingAddressSchema] = None
    tracking_number: Optional[str] = None
    estimated_delivery_date: Optional[str] = None
    actual_delivery_date: Optional[str] = None

    # Notes
    buyer_notes: Optional[str] = None
    supplier_notes: Optional[str] = None
    cancellation_reason: Optional[str] = None

    # Items
    order_items: Optional[List[OrderItemSchema]] = []
    items_count: Optional[int] = 0

    # Suivi (du plus ancien au plus récent)
    status_history: Optional[List[OrderStatusHistorySchema]] = []

    # Paiements — lus depuis la table `payments` (cf. OrderMapper), la commande
    # elle-même ne porte que `payment_status`.
    payment_method: Optional[PaymentMethod] = None
    #: Opérateur mobile money (orange, mtn…). Nul pour un paiement à la livraison.
    payment_provider: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CreateOrderSchema(BaseModel):
    """Schéma pour créer une commande depuis le panier.

    Deux façons de désigner la livraison :
      · `address_id` — une adresse du carnet ; le serveur la recopie. C'est le
        chemin normal depuis l'app.
      · `shipping_address` — l'adresse en clair, pour une livraison ponctuelle
        sans l'enregistrer au carnet.
    L'une des deux suffit ; `address_id` l'emporte si les deux sont fournies.
    """
    address_id: Optional[int] = Field(None, gt=0)
    shipping_address: Optional[ShippingAddressSchema] = None
    shipping_method: ShippingMethod = ShippingMethod.STANDARD
    payment_method: PaymentMethod
    #: Opérateur mobile money (orange, mtn, moov, wave) — requis pour ce moyen.
    payment_provider: Optional[str] = Field(None, max_length=100)
    #: Numéro à débiter — requis en mobile money.
    payment_phone: Optional[str] = Field(None, min_length=8, max_length=20)
    buyer_notes: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def require_an_address(self):
        if self.address_id is None and self.shipping_address is None:
            raise ValueError("Fournissez une adresse de livraison (address_id ou shipping_address)")
        return self

    @model_validator(mode="after")
    def require_mobile_money_details(self):
        """Un paiement mobile money sans opérateur ni numéro est inexploitable :
        le fournisseur ne saurait ni où ni qui débiter. On refuse à l'entrée
        plutôt que de créer une commande que personne ne peut encaisser.

        Les autres moyens (espèces à la livraison) n'en ont pas besoin.
        """
        if self.payment_method == PaymentMethod.MOBILE_MONEY:
            if not self.payment_provider:
                raise ValueError("Choisissez un opérateur mobile money")
            if not self.payment_phone:
                raise ValueError("Saisissez le numéro à débiter")
        return self


class UpdateOrderStatusSchema(BaseModel):
    """Schéma pour mettre à jour le statut d'une commande"""
    order_id: int = Field(..., gt=0)
    new_status: OrderStatus
    comment: Optional[str] = Field(None, max_length=500)


class CancelOrderSchema(BaseModel):
    """Schéma pour annuler une commande"""
    order_id: int = Field(..., gt=0)
    cancellation_reason: str = Field(..., min_length=10, max_length=500)


class QuoteItemSchema(BaseModel):
    """Une ligne du devis."""
    product_id: int
    product_name: str
    product_image_url: Optional[str] = None
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class QuoteSupplierSchema(BaseModel):
    """Le devis d'UN fournisseur.

    Valider le panier créera une commande par fournisseur (cf.
    OrderService.create_order_from_cart) : l'écran de paiement doit donc afficher
    autant de blocs que de fournisseurs, pas un total unique.
    """
    supplier_id: int
    supplier_name: Optional[str] = None
    items: List[QuoteItemSchema] = []
    subtotal: Decimal
    shipping_cost: Decimal
    total: Decimal
    #: Renseigné quand la livraison est offerte parce que le franco est atteint.
    free_shipping_applied: bool = False
    #: Montant restant à ajouter pour décrocher le franco (None = pas de franco).
    free_shipping_remaining: Optional[Decimal] = None


class QuoteSchema(BaseModel):
    """Devis complet du panier : ce qui sera EXACTEMENT facturé.

    Le client n'additionne rien lui-même — il affiche ces montants tels quels.
    """
    orders: List[QuoteSupplierSchema] = []
    subtotal: Decimal
    shipping_total: Decimal
    total: Decimal
    currency: str = "XOF"
    #: Nombre de commandes qui seront créées à la validation.
    orders_count: int = 0


class QuoteRequestSchema(BaseModel):
    """Corps du devis. L'adresse n'est pas nécessaire au barème actuel (il ne
    dépend pas de la zone) — le champ existe pour ne pas casser le contrat le
    jour où un barème par région arrivera."""
    shipping_method: ShippingMethod = ShippingMethod.STANDARD