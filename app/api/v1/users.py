"""
Routes utilisateur — profil entreprise du compte connecté.

- GET  /api/v1/users/me/company-profile  → mon profil entreprise
- PUT  /api/v1/users/me/company-profile  → créer/mettre à jour (upsert)
- POST /api/v1/users/me/roles/supplier   → ouvrir un espace vendeur (libre-service)
"""
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.core.logger import logger
from app.mappers.users_mapper import UsersMapper
from app.repositories.company_profile_repo import CompanyProfileRepository
from app.repositories.user_repo import UserRepository
from app.schemas.base import ResponseBase
from app.schemas.company import CompanyProfileUpdateSchema
from app.schemas.seller_upgrade import BecomeSupplierResponse, BecomeSupplierSchema
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def get_profile_repo(db: Session = Depends(get_db)) -> CompanyProfileRepository:
    return CompanyProfileRepository(db)


def get_user_repo(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(UserRepository(db), CompanyProfileRepository(db))


@router.get("/me/company-profile", response_model=ResponseBase)
async def get_my_company_profile(
    user_id: Annotated[int, Depends(get_current_user)],
    repo: Annotated[CompanyProfileRepository, Depends(get_profile_repo)],
):
    """Profil entreprise du compte connecté (peut être null)."""
    profile = repo.get_by_user_id(user_id)
    return ResponseBase(success=True, message="OK", item=_serialize(profile))


@router.put("/me/company-profile", response_model=ResponseBase)
async def update_my_company_profile(
    data: CompanyProfileUpdateSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    repo: Annotated[CompanyProfileRepository, Depends(get_profile_repo)],
):
    """Crée ou met à jour le profil entreprise (upsert)."""
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    profile = repo.get_by_user_id(user_id)
    if profile:
        profile = repo.update(profile.id, **fields)
    else:
        # company_name est obligatoire à la création
        fields.setdefault("company_name", fields.get("company_name") or "Mon entreprise")
        profile = repo.create(user_id=user_id, **fields)
    return ResponseBase(success=True, message="Profil mis à jour", item=_serialize(profile))


@router.post(
    "/me/roles/supplier",
    response_model=ResponseBase[BecomeSupplierResponse],
    status_code=status.HTTP_201_CREATED,
)
async def become_supplier(
    data: BecomeSupplierSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    profile_repo: Annotated[CompanyProfileRepository, Depends(get_profile_repo)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Ouvrir un espace vendeur sur un compte existant (attribution immédiate).

    Renvoie un **nouveau access_token** : les guards lisent les rôles dans le JWT
    (`deps.require_role`), donc sans remplacer son jeton le client aurait le rôle
    en base mais serait toujours refusé par l'API. Le client DOIT le stocker.

    Idempotent : rappeler la route sur un compte déjà vendeur met simplement à
    jour le profil entreprise et rafraîchit le jeton.
    """
    user = user_repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("Utilisateur", user_id)

    # Profil entreprise (upsert) — c'est l'identité commerciale du vendeur.
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    profile = profile_repo.get_by_user_id(user_id)
    if profile:
        profile_repo.update(profile.id, **fields)
    else:
        profile_repo.create(user_id=user_id, **fields)

    # `add_roles` est idempotent et dédoublonné : un compte déjà vendeur ne
    # gagne pas de doublon. On (re)pose aussi `buyer` — un vendeur reste acheteur.
    user_repo.add_roles(user_id, ["buyer", "supplier"])
    roles = user_repo.get_roles(user_id)

    # Jeton régénéré avec les nouveaux rôles.
    token = auth_service.create_access_token(user_id, user.user_type.value, roles)
    logger.info(f"User {user_id} a ouvert un espace vendeur — rôles: {roles}")

    # Relecture : `role_names` doit refléter les rôles qu'on vient d'ajouter.
    user = user_repo.get_by_id(user_id)

    return ResponseBase[BecomeSupplierResponse](
        success=True,
        message="Espace vendeur activé",
        item=BecomeSupplierResponse(
            access_token=token,
            token_type="bearer",
            roles=roles,
            user=UsersMapper.entity_to_schema(user),
        ),
    )


def _serialize(profile) -> dict | None:
    if not profile:
        return None
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "company_name": profile.company_name,
        "company_description": profile.company_description,
        "business_registration": profile.business_registration,
        "contact_person": profile.contact_person,
        "address": profile.address,
        "city": profile.city,
        "district": profile.district,
        "region": profile.region,
        "tax_id": profile.tax_id,
        "phone": profile.phone,
        "whatsapp": profile.whatsapp,
        "facebook": profile.facebook,
        "instagram": profile.instagram,
        "is_verified": profile.is_verified,
    }
