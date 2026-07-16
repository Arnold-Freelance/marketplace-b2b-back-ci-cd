"""
Routes v2 catégories — pattern REST idiomatique.

- POST   /api/v1/categories                créer
- GET    /api/v1/categories                lister (filtres en query)
- GET    /api/v1/categories/{id}           détail
- PUT    /api/v1/categories/{id}           modifier
- DELETE /api/v1/categories/{id}           supprimer (soft)
- GET    /api/v1/categories/by-slug/{slug} détail par slug
- GET    /api/v1/categories/hierarchy      arborescence complète

NB : list/get/hierarchy/by-slug sont publics (browsing).
     create/update/delete demandent un token (auth via AuthMiddleware).
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user, get_db, require_role
from app.repositories.category_repo import CategoryRepo
from app.repositories.product_repo import ProductRepository
from app.schemas.base import RequestBase, ResponseBase
from app.schemas.category import CategorySchema
from app.services.category_service_v2 import CategoryService

router = APIRouter(prefix="/api/v1/categories", tags=["Categories"])


def get_category_service(db: Session = Depends(get_db)) -> CategoryService:
    return CategoryService(CategoryRepo(db), ProductRepository(db))


@router.post("", response_model=ResponseBase[CategorySchema], status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategorySchema,
    current_user_id: Annotated[int, Depends(require_role("admin"))],
    service: Annotated[CategoryService, Depends(get_category_service)],
):
    """Créer une catégorie — réservé admin (T6)."""
    request = RequestBase[CategorySchema](user=current_user_id, data=data)
    return service.create(request)


@router.get("", response_model=ResponseBase[CategorySchema])
async def list_categories(
    current_user_id: Annotated[Optional[int], Depends(get_optional_user)],
    service: Annotated[CategoryService, Depends(get_category_service)],
    name: Optional[str] = Query(None, description="Recherche par nom"),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Liste des catégories (le service legacy exige un user, fourni via le token)."""
    criteria = CategorySchema(name=name, is_active=is_active)
    request = RequestBase[CategorySchema](
        user=current_user_id, limit=limit, offset=offset, data=criteria
    )
    return service.get_by_criteria(request)


@router.get("/{category_id}", response_model=ResponseBase[CategorySchema])
async def get_category(
    service: Annotated[CategoryService, Depends(get_category_service)],
    category_id: int = Path(..., gt=0),
):
    return service.get_by_id(category_id)


@router.put("/{category_id}", response_model=ResponseBase[CategorySchema])
async def update_category(
    data: CategorySchema,
    current_user_id: Annotated[int, Depends(require_role("admin"))],
    service: Annotated[CategoryService, Depends(get_category_service)],
    category_id: int = Path(..., gt=0),
):
    """Modifier une catégorie — réservé admin (T6)."""
    data.id = category_id
    request = RequestBase[CategorySchema](user=current_user_id, data=data)
    return service.update(request)


@router.delete("/{category_id}", response_model=ResponseBase[CategorySchema])
async def delete_category(
    current_user_id: Annotated[int, Depends(require_role("admin"))],
    service: Annotated[CategoryService, Depends(get_category_service)],
    category_id: int = Path(..., gt=0),
):
    """Supprimer (soft) une catégorie — réservé admin (T6)."""
    request = RequestBase[CategorySchema](
        user=current_user_id, data=CategorySchema(id=category_id)
    )
    return service.delete(request)


@router.get("/by-slug/{slug}", response_model=CategorySchema)
async def get_category_by_slug(
    service: Annotated[CategoryService, Depends(get_category_service)],
    slug: str = Path(...),
):
    return service.get_by_slug(slug)


@router.get("/hierarchy", response_model=list[CategorySchema])
async def get_category_hierarchy(
    service: Annotated[CategoryService, Depends(get_category_service)],
):
    """Arborescence complète des catégories."""
    return service.get_hierarchy()
