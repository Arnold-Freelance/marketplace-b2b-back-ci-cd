"""
Routes v2 produits — pattern REST idiomatique (Phase 3 code-facto).

Différences vs `v1/products.py` :
- Verbes HTTP corrects : GET pour list/read, POST pour create, PUT pour
  update, DELETE pour delete (au lieu de tout en POST avec /create, /update,
  /delete dans le path).
- Pas de RequestBase enveloppant : le body est le schema directement.
- Pas de `user` dans le body : l'identité vient de `request.state.user_id`
  (posé par AuthMiddleware), exposée via `Depends(get_current_user)`.
- Query params pour filtres/pagination (cacheable, idiomatique HTTP).
- ResponseBase auto-wrappé par `ResponseWrappingMiddleware` — le service
  peut retourner directement le schema ou la liste.

Migration mobile :
- /api/v1/products/* reste opérationnel pour la compat
- Quand le mobile bascule vers /api/v1/products/*, supprimer le v1.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user, get_db, require_role
from app.repositories.category_repo import CategoryRepo
from app.repositories.product_repo import ProductRepository
from app.repositories.user_repo import UserRepository
from app.schemas.base import RequestBase, ResponseBase
from app.schemas.product import ProductSchema
from app.services.product_service import ProductService

router = APIRouter(prefix="/api/v1/products", tags=["Products"])


def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    return ProductService(
        ProductRepository(db),
        CategoryRepo(db),
        UserRepository(db),
    )


# ==================== READ ====================

@router.get("", response_model=ResponseBase[ProductSchema])
async def list_products(
    current_user_id: Annotated[Optional[int], Depends(get_optional_user)],
    service: Annotated[ProductService, Depends(get_product_service)],
    search: Optional[str] = Query(None, description="Recherche full-text"),
    category_id: Optional[int] = Query(None, gt=0),
    category_slug: Optional[str] = Query(None, description="Filtrer par slug de catégorie"),
    supplier_id: Optional[int] = Query(None, gt=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    in_stock: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_featured: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Liste paginée des produits avec filtres en query params."""
    # Adapter au service legacy qui attend un RequestBase
    criteria = ProductSchema(
        search_query=search,
        category_id=category_id,
        category_slug=category_slug,
        supplier_id=supplier_id,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        is_active=is_active,
        is_featured=is_featured,
    )
    request = RequestBase[ProductSchema](
        user=current_user_id,
        limit=limit,
        offset=offset,
        data=criteria,
    )
    return service.get_by_criteria(request)


@router.get("/featured", response_model=ResponseBase[ProductSchema])
async def list_featured_products(
    current_user_id: Annotated[Optional[int], Depends(get_optional_user)],
    service: Annotated[ProductService, Depends(get_product_service)],
    limit: int = Query(10, ge=1, le=50),
):
    """Vitrine de l'accueil. Déclaré AVANT /{product_id}.

    Hybride : les produits `is_featured` d'abord (curation), complétés par les
    plus consultés (`views_count`) jusqu'à `limit`. Le filtre strict
    `is_featured=True` ne renvoyait que la poignée de produits marqués — soit
    cinq aujourd'hui, aucun back-office ne permettant d'en marquer d'autres.

    Pour filtrer *strictement* sur la curation, `GET /products?is_featured=true`
    reste disponible, avec pagination.
    """
    return service.get_showcase(limit)


@router.get("/recent", response_model=ResponseBase[ProductSchema])
async def list_recent_products(
    current_user_id: Annotated[Optional[int], Depends(get_optional_user)],
    service: Annotated[ProductService, Depends(get_product_service)],
    limit: int = Query(8, ge=1, le=50),
):
    """Produits récents (actifs). Déclaré AVANT /{product_id}."""
    criteria = ProductSchema(is_active=True)
    request = RequestBase[ProductSchema](user=current_user_id, limit=limit, offset=0, data=criteria)
    return service.get_by_criteria(request)


@router.get("/{product_id}", response_model=ResponseBase[ProductSchema])
async def get_product(
    service: Annotated[ProductService, Depends(get_product_service)],
    product_id: int = Path(..., gt=0),
):
    """Détail d'un produit. Public (pas d'auth requise pour browsing)."""
    return service.get_by_id(product_id)


# ==================== WRITE ====================

@router.post(
    "",
    response_model=ResponseBase[ProductSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    data: ProductSchema,
    current_user_id: Annotated[int, Depends(require_role("supplier", "admin"))],
    service: Annotated[ProductService, Depends(get_product_service)],
):
    """Crée un produit (réservé supplier/admin — T6).

    - supplier → le produit lui appartient.
    - admin → doit fournir `supplier_id` dans le body (création au nom du fournisseur).
    L'autorisation fine est aussi revérifiée dans le service.
    """
    request = RequestBase[ProductSchema](user=current_user_id, data=data)
    return service.create(request)


@router.put("/{product_id}", response_model=ResponseBase[ProductSchema])
async def update_product(
    data: ProductSchema,
    current_user_id: Annotated[int, Depends(require_role("supplier", "admin"))],
    service: Annotated[ProductService, Depends(get_product_service)],
    product_id: int = Path(..., gt=0),
):
    """Met à jour un produit (supplier/admin). L'autorisation fine (propriétaire
    OU admin) est revérifiée par le service."""
    data.id = product_id  # forcer l'id depuis le path
    request = RequestBase[ProductSchema](user=current_user_id, data=data)
    return service.update(request)


@router.delete("/{product_id}", response_model=ResponseBase[ProductSchema])
async def delete_product(
    current_user_id: Annotated[int, Depends(require_role("supplier", "admin"))],
    service: Annotated[ProductService, Depends(get_product_service)],
    product_id: int = Path(..., gt=0),
):
    """Soft delete d'un produit (propriétaire OU admin — vérifié par le service)."""
    request = RequestBase[ProductSchema](
        user=current_user_id,
        data=ProductSchema(id=product_id),
    )
    return service.delete(request)


# ==================== STOCK (action métier dédiée) ====================

@router.patch("/{product_id}/stock", response_model=ResponseBase[ProductSchema])
async def update_stock(
    quantity: Annotated[int, Query(ge=0, description="Nouvelle quantité en stock")],
    current_user_id: Annotated[int, Depends(require_role("supplier", "admin"))],
    service: Annotated[ProductService, Depends(get_product_service)],
    product_id: int = Path(..., gt=0),
):
    """Met à jour uniquement le stock (propriétaire OU admin — vérifié par le service)."""
    return service.update_stock(product_id, quantity, current_user_id)
