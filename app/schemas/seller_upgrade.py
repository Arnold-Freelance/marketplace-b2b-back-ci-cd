# app/schemas/seller_upgrade.py
"""Passage d'un compte acheteur en compte vendeur (libre-service)."""
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.user import UserSchema


class BecomeSupplierSchema(BaseModel):
    """Informations d'entreprise exigées pour ouvrir un espace vendeur.

    `company_name` est le seul champ obligatoire : c'est le nom sous lequel les
    acheteurs verront les produits. Le reste enrichit la fiche et peut être
    complété plus tard depuis le profil vendeur.
    """
    company_name: str = Field(..., min_length=2, max_length=255)
    company_description: Optional[str] = None
    business_registration: Optional[str] = Field(None, max_length=100)
    contact_person: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    tax_id: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    whatsapp: Optional[str] = Field(None, max_length=30)

    # Barème de livraison — réglable dès l'inscription (0 = livraison offerte).
    shipping_base_cost: Optional[Decimal] = Field(None, ge=0)
    free_shipping_threshold: Optional[Decimal] = Field(None, ge=0)


class BecomeSupplierResponse(BaseModel):
    """Réponse au passage vendeur.

    ⚠️ `access_token` est indispensable : les guards d'autorisation lisent les
    rôles DANS le JWT (cf. `deps.require_role`), pas en base. Sans jeton
    rafraîchi, l'utilisateur aurait le rôle en base mais resterait refusé par
    l'API jusqu'à sa prochaine reconnexion. Le client DOIT remplacer son jeton
    par celui-ci.
    """
    access_token: str
    token_type: str = "bearer"
    roles: List[str]
    user: UserSchema
