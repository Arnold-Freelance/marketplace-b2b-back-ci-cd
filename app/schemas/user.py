from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.core.enums import UserType, UserStatus
from app.schemas.schema_base import SchemaBase


class User(SchemaBase):
    phone_number: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    password: Optional[str] = None
    user_status: Optional[UserStatus] = True
    user_type: Optional[UserType] = None
    last_login: Optional[str] = None

    #Other informations
    #TODO: Adding the object create information associated like Company info


class UserSchema(BaseModel):
    id: int
    email: str
    phone: str
    user_type: UserType
    # Liste de rôles (T5) : source de vérité pour le frontend (switch d'espace).
    roles: List[str] = Field(default_factory=list)
    status: UserStatus
    created_at: str
    email_verified: bool
    phone_verified: bool
    last_login: Optional[str]

    # Profil entreprise si disponible
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    city: Optional[str] = None
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

class UserCreateSchema(BaseModel):
    email: EmailStr
    phone: str
    password: str
    user_type: UserType
    company_name: str
    contact_person: str
    city: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if not v.startswith(('+225', '225', '0')):
            raise ValueError('Numéro de téléphone ivoirien requis')
        return v

class UserLoginSchema(BaseModel):
    identifier: str
    password: str

class TokenResponse(BaseModel):
    """Schéma de réponse avec token"""
    access_token: str
    token_type: str = "bearer"
    user: UserSchema

class ForgotPasswordSchema(BaseModel):
    email: str

class VerifyResetCodeSchema(BaseModel):
    """Vérification du code à 6 chiffres reçu par email."""
    email: str
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")

class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str