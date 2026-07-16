"""
Routes v2 images produit — pattern REST nested resource.

Sous-ressource d'un produit (`/api/v1/products/{product_id}/images`).

- POST   /api/v1/products/{product_id}/images          upload une image
- POST   /api/v1/products/{product_id}/images/batch    upload multiple (max 10)
- GET    /api/v1/products/{product_id}/images          liste des images
- DELETE /api/v1/products/{product_id}/images/{id}     suppression
- PUT    /api/v1/products/{product_id}/images/{id}/primary  définir comme principale
- PUT    /api/v1/products/{product_id}/images/order    réorganiser
"""
from typing import Annotated, List

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Path, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.repositories.product_image_repo import ProductImageRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.user_repo import UserRepository
from app.schemas.product_image import ProductImageCreateSchema, ProductImageSchema
from app.services.file_upload_service import FileUploadService
from app.services.product_image_service import ProductImageService

router = APIRouter(prefix="/api/v1/products", tags=["Product Images"])


def get_product_image_service(db: Session = Depends(get_db)) -> ProductImageService:
    return ProductImageService(
        ProductImageRepository(db),
        ProductRepository(db),
        FileUploadService(base_upload_dir="uploads"),
        UserRepository(db),
    )


@router.post(
    "/{product_id}/images",
    response_model=ProductImageSchema,
    status_code=status.HTTP_201_CREATED,
)
async def upload_image(
    file: Annotated[UploadFile, File(description="Image (JPG/PNG/GIF/WEBP)")],
    current_user_id: Annotated[int, Depends(require_role("supplier", "admin"))],
    service: Annotated[ProductImageService, Depends(get_product_image_service)],
    product_id: int = Path(..., gt=0),
    display_order: int = Form(0),
    is_primary: bool = Form(False),
    alt_text: str = Form(None),
):
    """Upload une image (créée + thumbnail). Réservé au propriétaire du produit."""
    schema = ProductImageCreateSchema(
        product_id=product_id,
        display_order=display_order,
        is_primary=is_primary,
        alt_text=alt_text,
    )
    return await service.upload_and_create(file, schema, current_user_id)


@router.post(
    "/{product_id}/images/batch",
    response_model=List[ProductImageSchema],
    status_code=status.HTTP_201_CREATED,
)
async def upload_images_batch(
    files: Annotated[List[UploadFile], File(description="Liste d'images (max 10)")],
    current_user_id: Annotated[int, Depends(require_role("supplier", "admin"))],
    service: Annotated[ProductImageService, Depends(get_product_image_service)],
    product_id: int = Path(..., gt=0),
):
    if len(files) > 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Maximum 10 images par requête")
    return await service.upload_multiple(files, product_id, current_user_id)


@router.get("/{product_id}/images", response_model=List[ProductImageSchema])
async def list_product_images(
    service: Annotated[ProductImageService, Depends(get_product_image_service)],
    product_id: int = Path(..., gt=0),
):
    """Liste publique des images d'un produit, triée par display_order."""
    return service.get_product_images(product_id)


@router.delete("/{product_id}/images/{image_id}")
async def delete_product_image(
    current_user_id: Annotated[int, Depends(require_role("supplier", "admin"))],
    service: Annotated[ProductImageService, Depends(get_product_image_service)],
    product_id: int = Path(..., gt=0),
    image_id: int = Path(..., gt=0),
):
    service.delete_image(image_id, current_user_id)
    return {"message": "Image supprimée"}


@router.put("/{product_id}/images/{image_id}/primary")
async def set_primary_image(
    current_user_id: Annotated[int, Depends(require_role("supplier", "admin"))],
    service: Annotated[ProductImageService, Depends(get_product_image_service)],
    product_id: int = Path(..., gt=0),
    image_id: int = Path(..., gt=0),
):
    """Définir cette image comme image principale du produit (propriétaire OU admin — T6)."""
    service.set_primary_image(image_id, product_id, current_user_id)
    return {"message": "Image principale mise à jour"}


@router.put("/{product_id}/images/order")
async def reorder_product_images(
    image_orders: Annotated[
        dict,
        Body(
            description="Mapping {image_id: nouvelle_position}",
            example={"1": 0, "2": 1, "3": 2},
        ),
    ],
    current_user_id: Annotated[int, Depends(require_role("supplier", "admin"))],
    service: Annotated[ProductImageService, Depends(get_product_image_service)],
    product_id: int = Path(..., gt=0),
):
    """Réorganiser les images (propriétaire OU admin — T6)."""
    service.reorder_images(product_id, image_orders, current_user_id)
    return {"message": "Images réorganisées"}
