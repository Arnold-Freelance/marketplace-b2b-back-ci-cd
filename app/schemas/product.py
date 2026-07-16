# app/schemas/product.py
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.product_image import ProductImageSchema, ProductDocumentSchema
from app.schemas.schema_base import SchemaBase


class ProductSchema(SchemaBase):
    """Schéma principal pour Product avec tous les champs"""
    id: Optional[int] = None
    supplier_id: Optional[int] = None
    category_id: Optional[int] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[Decimal] = None
    # Prix de référence avant remise : le client affiche un prix barré si et
    # seulement si `original_price > price`.
    original_price: Optional[Decimal] = None
    # ⚠️ Ces trois champs DOIVENT valoir None par défaut, pas une valeur métier.
    # `ProductSchema` sert aussi de corps au PUT, et le @model_serializer de MyBase
    # ne droppe que les None : un défaut non-nul est donc RÉÉCRIT en base à chaque
    # mise à jour qui ne renvoie pas le champ. `stock_quantity = 0` remettait ainsi
    # le stock à zéro (même piège que le défaut `[]` qui effaçait les images).
    # À la création, les valeurs par défaut viennent des colonnes SQL
    # (currency='XOF', min_order_quantity=1, stock_quantity=0).
    currency: Optional[str] = None
    min_order_quantity: Optional[int] = None
    stock_quantity: Optional[int] = None
    unit: Optional[str] = None
    shipping_cost_override: Optional[Decimal] = None
    # images: Optional[List[str]] = None  # Liste d'URLs d'images
    attributes: Optional[Dict[str, Any]] = None  # Attributs JSON personnalisés
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    views_count: Optional[int] = 0

    # Agrégats d'avis (calculés, réponse-seule : défaut None pour être exclus
    # de model_dump(exclude_none=True) côté create/update — ce sont des
    # @property en lecture seule sur l'entité, non assignables).
    average_rating: Optional[float] = None
    reviews_count: Optional[int] = None

    # Relations
    supplier_name: Optional[str] = None
    supplier_email: Optional[str] = None
    supplier_is_verified: Optional[bool] = None
    category_name: Optional[str] = None
    category_slug: Optional[str] = None

    # Champs de recherche
    search_query: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    in_stock: Optional[bool] = None

    # Liste d'images et documents
    product_images: Optional[List[ProductImageSchema]] = []
    # product_documents: Optional[List[ProductDocumentSchema]] = []

    # Image principale (pour affichage rapide)
    primary_image_url: Optional[str] = None
    primary_thumbnail_url: Optional[str] = None

    @field_validator('price')
    @classmethod
    def validate_price(cls, v):
        """Valider que le prix est positif"""
        if v is not None and v < 0:
            raise ValueError("Le prix doit être positif")
        return v

    @field_validator('min_order_quantity', 'stock_quantity')
    @classmethod
    def validate_quantities(cls, v):
        """Valider que les quantités sont positives"""
        if v is not None and v < 0:
            raise ValueError("La quantité doit être positive")
        return v

    @model_validator(mode="after")
    def check_original_price(self):
        """Un prix de référence sous le prix de vente ne décrit aucune remise :
        le refuser plutôt que d'afficher un prix barré absurde.

        Ne se déclenche que si les deux prix arrivent ensemble — une mise à jour
        partielle (stock seul) ne doit pas être bloquée. Envoyer `original_price = 0`
        est la façon de retirer une promotion.
        """
        if (
            self.original_price is not None
            and self.price is not None
            and self.original_price > 0
            and self.original_price <= self.price
        ):
            raise ValueError("Le prix d'origine doit être supérieur au prix de vente")
        return self

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "iPhone 15 Pro",
                "slug": "iphone-15-pro",
                "description": "Dernier smartphone Apple",
                "short_description": "iPhone 15 Pro 256GB",
                "sku": "IPH15P-256",
                "price": 1299000,
                "currency": "XOF",
                "min_order_quantity": 1,
                "stock_quantity": 50,
                "unit": "pièce",
                "category_id": 1,
                "is_active": True,
                "is_featured": True
            }
        },
    )


# ⚠️ Les deux schémas ci-dessous ne sont utilisés NULLE PART : les routes
# `POST /products` et `PUT /products/{id}` prennent toutes deux `ProductSchema`.
# Conservés tels quels ; toute évolution du contrat produit doit se faire sur
# `ProductSchema` tant que les routes ne sont pas migrées.

class ProductCreateSchema(SchemaBase):
    """Schéma pour la création d'un produit"""
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=255)
    category_id: int = Field(..., gt=0)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=500)
    sku: Optional[str] = Field(None, max_length=100)
    price: Decimal = Field(..., gt=0)
    currency: str = Field(default="XOF", max_length=3)
    min_order_quantity: int = Field(default=1, ge=1)
    stock_quantity: int = Field(default=0, ge=0)
    unit: Optional[str] = Field(None, max_length=50)
    images: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    is_active: bool = True
    is_featured: bool = False


class ProductUpdateSchema(SchemaBase):
    """Schéma pour la mise à jour d'un produit"""
    id: int = Field(..., gt=0)
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255)
    category_id: Optional[int] = Field(None, gt=0)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=500)
    sku: Optional[str] = Field(None, max_length=100)
    price: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=3)
    min_order_quantity: Optional[int] = Field(None, ge=1)
    stock_quantity: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=50)
    images: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None