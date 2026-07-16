"""
Routes espace fournisseur.

- GET /api/v1/supplier/dashboard        → tableau de bord du fournisseur connecté
- GET /api/v1/suppliers                 → annuaire public des fournisseurs
- GET /api/v1/suppliers/{id}            → profil public d'un fournisseur
- GET /api/v1/suppliers/{id}/products   → produits d'un fournisseur
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user, get_db, require_role
from app.core.exceptions import NotFoundError
from app.repositories.category_repo import CategoryRepo
from app.repositories.product_repo import ProductRepository
from app.repositories.user_repo import UserRepository
from app.schemas.base import RequestBase, ResponseBase
from app.schemas.product import ProductSchema
from app.services.product_service import ProductService
from app.services.supplier_service import SupplierService

router = APIRouter(prefix="/api/v1/supplier", tags=["Supplier"])
# Routeur public (vue acheteur sur un fournisseur) — préfixe pluriel.
public_router = APIRouter(prefix="/api/v1/suppliers", tags=["Suppliers"])


def get_supplier_service(db: Session = Depends(get_db)) -> SupplierService:
    return SupplierService(db)


def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    return ProductService(ProductRepository(db), CategoryRepo(db), UserRepository(db))


@router.get("/dashboard")
async def supplier_dashboard(
    current_user_id: Annotated[int, Depends(require_role("supplier"))],
    service: Annotated[SupplierService, Depends(get_supplier_service)],
):
    """Indicateurs du tableau de bord pour le fournisseur connecté — réservé supplier (T6)."""
    return service.get_dashboard(current_user_id)


@public_router.get("", response_model=ResponseBase)
async def list_suppliers(
    current_user_id: Annotated[Optional[int], Depends(get_optional_user)],
    service: Annotated[SupplierService, Depends(get_supplier_service)],
    search: Optional[str] = Query(None, max_length=120, description="Filtre sur le nom d'entreprise"),
    city: Optional[str] = Query(None, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Annuaire public des fournisseurs (vérifiés d'abord, puis les mieux notés)."""
    items, total = service.list_public(limit=limit, offset=offset, search=search, city=city)
    return ResponseBase(success=True, message="OK", items=items, total=total)


@public_router.get("/{supplier_id}", response_model=ResponseBase)
async def get_supplier_profile(
    current_user_id: Annotated[Optional[int], Depends(get_optional_user)],
    db: Annotated[Session, Depends(get_db)],
    supplier_id: int = Path(..., gt=0),
):
    """Profil public d'un fournisseur (infos entreprise + réputation)."""
    user = UserRepository(db).get_by_id(supplier_id, raise_if_missing=False)
    if not user:
        raise NotFoundError("Fournisseur", supplier_id)

    profile = getattr(user, "company_profile", None)
    item = {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "company_name": profile.company_name if profile else None,
        "company_description": getattr(profile, "company_description", None) if profile else None,
        "contact_person": profile.contact_person if profile else None,
        "address": getattr(profile, "address", None) if profile else None,
        "city": profile.city if profile else None,
        "is_verified": profile.is_verified if profile else False,
        "average_rating": getattr(user, "average_rating", 0.0),
        "total_reviews": getattr(user, "total_reviews_count", 0),
    }
    return ResponseBase(success=True, message="OK", item=item)


@public_router.get("/{supplier_id}/products", response_model=ResponseBase[ProductSchema])
async def get_supplier_products(
    current_user_id: Annotated[Optional[int], Depends(get_optional_user)],
    service: Annotated[ProductService, Depends(get_product_service)],
    supplier_id: int = Path(..., gt=0),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Produits actifs d'un fournisseur."""
    criteria = ProductSchema(supplier_id=supplier_id, is_active=True)
    request = RequestBase[ProductSchema](
        user=current_user_id, limit=limit, offset=offset, data=criteria
    )
    return service.get_by_criteria(request)
