from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class CompanyProfileSchema(BaseModel):
    id: int
    company_name: str
    contact_person: Optional[str]
    city: Optional[str]
    phone: Optional[str]
    is_verified: bool

    # Barème de livraison du fournisseur (cf. OrderService.compute_shipping_cost).
    shipping_base_cost: Optional[Decimal] = None
    free_shipping_threshold: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class CompanyProfileUpdateSchema(BaseModel):
    """Champs modifiables du profil entreprise (tous optionnels)."""
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    business_registration: Optional[str] = None
    contact_person: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    region: Optional[str] = None
    tax_id: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None

    # Livraison. `free_shipping_threshold = 0` retire le franco (le laisser à
    # None signifie « ne pas toucher au réglage existant »).
    shipping_base_cost: Optional[Decimal] = Field(None, ge=0)
    free_shipping_threshold: Optional[Decimal] = Field(None, ge=0)
