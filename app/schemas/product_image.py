# ================================================
# app/schemas/product_image.py
# ================================================
"""
Schémas pour les images de produits
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ProductImageSchema(BaseModel):
    """Schéma pour une image de produit"""
    id: Optional[int] = None
    product_id: Optional[int] = None
    image_url: str
    thumbnail_url: Optional[str] = None
    display_order: int = 0
    is_primary: bool = False
    alt_text: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProductImageCreateSchema(BaseModel):
    """Schéma pour créer une image de produit"""
    product_id: int = Field(..., gt=0)
    display_order: int = Field(default=0, ge=0)
    is_primary: bool = False
    alt_text: Optional[str] = Field(None, max_length=255)


class ProductDocumentSchema(BaseModel):
    """Schéma pour un document de produit"""
    id: Optional[int] = None
    product_id: Optional[int] = None
    document_url: str
    document_type: Optional[str] = None
    title: str
    description: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)