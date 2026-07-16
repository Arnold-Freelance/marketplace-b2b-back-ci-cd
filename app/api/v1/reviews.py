"""
Routes v2 avis (reviews) — pattern REST idiomatique.

- POST  /api/v1/reviews                       créer un avis
- PUT   /api/v1/reviews/{id}                  modifier
- POST  /api/v1/reviews/{id}/response         réponse fournisseur
- POST  /api/v1/reviews/{id}/vote             vote utile
- GET   /api/v1/reviews                       mes avis (role=author ou supplier)
- GET   /api/v1/reviews/products/{id}         avis d'un produit
- GET   /api/v1/reviews/statistics            statistiques (product_id ou user_id en query)
"""
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.repositories.device_token_repo import DeviceTokenRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.review_repo import (
    ReviewHelpfulVoteRepository,
    ReviewRepository,
)
from app.repositories.user_repo import UserRepository
from app.schemas.base import ResponseBase
from app.schemas.review import (
    CreateReviewSchema,
    ReviewHelpfulVoteSchema,
    ReviewSchema,
    ReviewStatisticsSchema,
    SupplierResponseSchema,
    UpdateReviewSchema,
)
from app.services.notification_service import NotificationService
from app.services.push.dispatcher import PushDispatcher
from app.services.review_service import ReviewService

router = APIRouter(prefix="/api/v1/reviews", tags=["Reviews"])


def get_review_service(db: Session = Depends(get_db)) -> ReviewService:
    return ReviewService(
        ReviewRepository(db),
        ReviewHelpfulVoteRepository(db),
        OrderRepository(db),
        ProductRepository(db),
        UserRepository(db),
        notification_service=NotificationService(
            NotificationRepository(db),
            push_dispatcher=PushDispatcher(DeviceTokenRepository(db)),
        ),
    )


@router.post("", response_model=ResponseBase[ReviewSchema], status_code=status.HTTP_201_CREATED)
async def create_review(
    data: CreateReviewSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
):
    """Créer un avis (commande livrée requise, 1 avis max par commande)."""
    return await service.create_review(user_id, data)


@router.put("/{review_id}", response_model=ResponseBase[ReviewSchema])
async def update_review(
    data: UpdateReviewSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
    review_id: int = Path(..., gt=0),
):
    data.review_id = review_id
    return service.update_review(user_id, data)


@router.post("/{review_id}/response", response_model=ResponseBase[ReviewSchema])
async def add_supplier_response(
    data: SupplierResponseSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
    review_id: int = Path(..., gt=0),
):
    """Réponse du fournisseur évalué (1 seule réponse par avis)."""
    data.review_id = review_id
    return service.add_supplier_response(user_id, data)


@router.post("/{review_id}/vote", response_model=ResponseBase[ReviewSchema])
async def vote_helpful(
    data: ReviewHelpfulVoteSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
    review_id: int = Path(..., gt=0),
):
    """Voter utile/pas utile (1 vote par user, modifiable)."""
    data.review_id = review_id
    return service.vote_helpful(user_id, data)


@router.get("", response_model=ResponseBase[ReviewSchema])
async def list_my_reviews(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[ReviewService, Depends(get_review_service)],
    role: Literal["author", "supplier"] = Query(
        "author", description="author = mes avis donnés, supplier = avis reçus"
    ),
):
    return service.get_user_reviews(user_id, as_reviewer=(role == "author"))


@router.get("/products/{product_id}", response_model=ResponseBase[ReviewSchema])
async def list_product_reviews(
    service: Annotated[ReviewService, Depends(get_review_service)],
    product_id: int = Path(..., gt=0),
    sort_by: Literal["recent", "helpful", "rating_high", "rating_low"] = Query("recent"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Avis publics d'un produit. Public (pas d'auth nécessaire)."""
    return service.get_product_reviews(product_id, limit, offset, sort_by)


@router.get("/statistics", response_model=ResponseBase[ReviewStatisticsSchema])
async def get_review_statistics(
    service: Annotated[ReviewService, Depends(get_review_service)],
    product_id: Optional[int] = Query(None, gt=0),
    user_id: Optional[int] = Query(None, gt=0),
):
    """
    Statistiques d'avis.
    - `?product_id=X` : stats d'un produit
    - `?user_id=X`   : stats d'un fournisseur
    """
    if product_id:
        return service.get_review_statistics(product_id=product_id)
    if user_id:
        return service.get_review_statistics(user_id=user_id)
    return service.get_review_statistics()
