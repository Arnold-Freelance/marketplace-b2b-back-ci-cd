"""
Schémas pour le panier d'achat
"""
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.schema_base import SchemaBase


class CartItemSchema(SchemaBase):
    """Schéma pour un item du panier"""
    id: Optional[int] = None
    cart_id: Optional[int] = None
    product_id: Optional[int] = None
    quantity: int = Field(default=1, ge=1)
    unit_price: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None

    # Informations du produit (enrichies)
    product_name: Optional[str] = None
    product_slug: Optional[str] = None
    product_image_url: Optional[str] = None
    product_stock: Optional[int] = None
    is_available: Optional[bool] = True

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CartSchema(SchemaBase):
    """Schéma pour le panier"""
    id: Optional[int] = None
    user_id: Optional[int] = None
    is_active: bool = True
    session_id: Optional[str] = None

    # Items du panier
    cart_items: Optional[List[CartItemSchema]] = []

    # Totaux calculés
    items_count: Optional[int] = 0
    subtotal: Optional[Decimal] = Decimal("0.00")

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AddToCartSchema(BaseModel):
    """Schéma pour ajouter au panier"""
    product_id: int = Field(..., gt=0)
    quantity: int = Field(default=1, ge=1)


class UpdateCartItemSchema(BaseModel):
    """Schéma pour mettre à jour un item du panier"""
    cart_item_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=1)


class MergeCartItemSchema(BaseModel):
    """Un item du panier invité à fusionner."""
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=1)


class MergeCartSchema(BaseModel):
    """Panier invité (client) à fusionner dans le panier serveur à la connexion.

    Les quantités s'additionnent au panier serveur, dédoublonnées par produit.
    La fusion est tolérante : un produit devenu indisponible est ignoré, une
    quantité au-delà du stock est plafonnée (jamais d'échec global).
    """
    items: List[MergeCartItemSchema] = Field(default_factory=list)