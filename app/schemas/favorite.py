"""
Schémas pour les favoris/wishlist
"""
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.schema_base import SchemaBase


class FavoriteSchema(SchemaBase):
    """Schéma pour un favori"""
    id: Optional[int] = None
    user_id: Optional[int] = None
    product_id: Optional[int] = None
    notes: Optional[str] = None
    priority: int = 0
    notification_enabled: bool = True
    price_at_add: Optional[Decimal] = None

    # Informations du produit (enrichies)
    product_name: Optional[str] = None
    product_slug: Optional[str] = None
    product_price: Optional[Decimal] = None
    product_image: Optional[str] = None
    product_is_available: Optional[bool] = True
    product_stock: Optional[int] = 0

    # Alertes
    price_dropped: Optional[bool] = False  # Prix a baissé depuis l'ajout
    price_difference: Optional[Decimal] = None  # Différence de prix

    created_at: Optional[str] = None


class AddToFavoritesSchema(BaseModel):
    """Schéma pour ajouter aux favoris"""
    product_id: int = Field(..., gt=0)
    notes: Optional[str] = Field(None, max_length=500)
    priority: int = Field(default=0, ge=0, le=5)
    notification_enabled: bool = True


class UpdateFavoriteSchema(BaseModel):
    """Schéma pour mettre à jour un favori"""
    favorite_id: int = Field(..., gt=0)
    notes: Optional[str] = Field(None, max_length=500)
    priority: Optional[int] = Field(None, ge=0, le=5)
    notification_enabled: Optional[bool] = None


class FavoriteStatisticsSchema(BaseModel):
    """Schéma pour les statistiques des favoris"""
    total_favorites: int = 0
    available_products: int = 0
    unavailable_products: int = 0
    products_with_price_drop: int = 0
    total_potential_savings: Decimal = Decimal("0.00")