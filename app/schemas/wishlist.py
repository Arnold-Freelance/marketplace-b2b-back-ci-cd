# ================================================
# app/schemas/wishlist.py
# ================================================
"""
Schémas pour la liste de souhaits
"""
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from app.models.order_entity import PaymentStatus, ShippingMethod
from app.schemas.schema_base import SchemaBase

class WishlistItemSchema(SchemaBase):
    """Schéma pour un item de la wishlist"""
    id: Optional[int] = None
    user_id: Optional[int] = None
    product_id: Optional[int] = None
    notes: Optional[str] = None

    # Informations du produit
    product_name: Optional[str] = None
    product_slug: Optional[str] = None
    product_price: Optional[Decimal] = None
    product_image_url: Optional[str] = None
    product_is_available: Optional[bool] = True

    created_at: Optional[str] = None


class AddToWishlistSchema(BaseModel):
    """Schéma pour ajouter à la wishlist"""
    product_id: int = Field(..., gt=0)
    notes: Optional[str] = Field(None, max_length=500)