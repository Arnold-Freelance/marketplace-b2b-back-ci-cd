# app/schemas/address.py
"""Schémas du carnet d'adresses."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.order import ShippingAddressSchema


class AddressSchema(BaseModel):
    """Une adresse du carnet."""
    id: int
    label: Optional[str] = None
    full_name: str
    phone: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: str
    landmark: Optional[str] = None
    is_default: bool

    model_config = ConfigDict(from_attributes=True)

    def to_shipping_address(self) -> ShippingAddressSchema:
        """Adresse figée dans la commande. Les champs sont alignés sur
        `ShippingAddressSchema`, la conversion est donc une simple projection."""
        return ShippingAddressSchema(
            full_name=self.full_name,
            phone=self.phone,
            address_line1=self.address_line1,
            address_line2=self.address_line2,
            city=self.city,
            state=self.state,
            postal_code=self.postal_code,
            country=self.country,
        )


class AddressCreateSchema(BaseModel):
    """Création d'une adresse."""
    label: Optional[str] = Field(None, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=8, max_length=20)
    address_line1: str = Field(..., min_length=5, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: str = Field(default="Côte d'Ivoire", max_length=100)
    landmark: Optional[str] = None
    is_default: bool = False


class AddressUpdateSchema(BaseModel):
    """Mise à jour partielle : seuls les champs fournis sont modifiés.

    Tous optionnels et à None par défaut — le service ne persiste que ce qui est
    explicitement envoyé (`model_dump(exclude_unset=True)`), pour ne pas effacer
    un champ qu'on n'a pas voulu toucher.
    """
    label: Optional[str] = Field(None, max_length=100)
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, min_length=8, max_length=20)
    address_line1: Optional[str] = Field(None, min_length=5, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    landmark: Optional[str] = None
    is_default: Optional[bool] = None
