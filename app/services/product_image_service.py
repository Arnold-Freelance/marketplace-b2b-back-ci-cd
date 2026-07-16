# ================================================
# app/services/product_image_service.py
# ================================================
"""
Service pour gérer les images de produits avec upload
"""
from typing import List
from fastapi import UploadFile, HTTPException, status
from PIL import Image
import io

from app.repositories.product_image_repo import ProductImageRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.user_repo import UserRepository
from app.services.file_upload_service import FileUploadService
from app.schemas.product_image import ProductImageSchema, ProductImageCreateSchema
from app.core.logger import logger


class ProductImageService:
    """Service pour gérer les images de produits"""

    def __init__(
            self,
            product_image_repo: ProductImageRepository,
            product_repo: ProductRepository,
            file_service: FileUploadService,
            user_repo: UserRepository,
    ):
        self.product_image_repo = product_image_repo
        self.product_repo = product_repo
        self.file_service = file_service
        self.user_repo = user_repo

    # ==================== AUTORISATION (T6) ====================

    def _roles_of(self, user_id: int) -> set:
        user = self.user_repo.get_by_id(user_id, raise_if_missing=False)
        return set(user.role_names) if user else set()

    def _ensure_can_manage(self, product_id: int, user_id: int):
        """Vérifie que le produit existe et que le caller peut le gérer.

        Autorisé si **propriétaire du produit OU admin** (T6). Renvoie l'entité
        produit. 404 si absent, 403 si non autorisé.
        """
        product = self.product_repo.get_by_id(product_id, raise_if_missing=False)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produit {product_id} non trouvé",
            )
        if product.supplier_id != user_id and "admin" not in self._roles_of(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'êtes pas autorisé à gérer les images de ce produit",
            )
        return product

    async def upload_and_create(
            self,
            file: UploadFile,
            schema: ProductImageCreateSchema,
            user_id: int
    ) -> ProductImageSchema:
        """
        Uploader une image et créer l'enregistrement en base

        Args:
            file: Fichier image uploadé
            schema: Données de l'image
            user_id: ID de l'utilisateur

        Returns:
            ProductImageSchema créé
        """
        # Vérifier existence + autorisation (propriétaire OU admin — T6)
        self._ensure_can_manage(schema.product_id, user_id)

        # CORRECTION: Lire le fichier UNE SEULE FOIS
        contents = await file.read()

        # Vérifier que le fichier n'est pas vide
        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier est vide"
            )

        # Récupérer les dimensions de l'image
        try:
            image = Image.open(io.BytesIO(contents))
            width, height = image.size

            # Vérifier que c'est bien une image valide
            image.verify()

            # Rouvrir l'image car verify() ferme le fichier
            image = Image.open(io.BytesIO(contents))

        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture de l'image: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fichier image invalide: {str(e)}"
            )

        # CORRECTION: Réinitialiser le pointeur du fichier avant l'upload
        # Créer un nouveau UploadFile avec le contenu déjà lu
        file.file = io.BytesIO(contents)
        await file.seek(0)

        # Uploader le fichier
        try:
            upload_result = await self.file_service.upload_product_image(
                file,
                create_thumbnail=True
            )
        except Exception as e:
            logger.error(f"Erreur lors de l'upload du fichier: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur lors de l'upload: {str(e)}"
            )

        # Créer l'enregistrement en base
        image_data = {
            "product_id": schema.product_id,
            "image_url": upload_result["original"],
            "thumbnail_url": upload_result.get("thumbnail"),
            "display_order": schema.display_order,
            "is_primary": schema.is_primary,
            "alt_text": schema.alt_text or file.filename,
            "file_name": file.filename,
            "file_size": len(contents),
            "width": width,
            "height": height,
            "created_by": user_id,
            "is_deleted": False
        }

        # Si c'est marqué comme primary, retirer le flag des autres
        if schema.is_primary:
            self.product_image_repo.set_as_primary(0, schema.product_id)

        image_entity = self.product_image_repo.create(**image_data)


        logger.info(f"Image créée pour produit {schema.product_id}: {image_entity.id}")

        return ProductImageSchema.model_validate(image_entity)

    async def upload_multiple(
            self,
            files: List[UploadFile],
            product_id: int,
            user_id: int
    ) -> List[ProductImageSchema]:
        """Uploader plusieurs images pour un produit"""
        # Autorisation vérifiée une fois en amont (fail fast) — évite d'uploader
        # des fichiers avant de rejeter (upload_and_create revérifie de toute façon).
        self._ensure_can_manage(product_id, user_id)

        results = []

        for index, file in enumerate(files):
            schema = ProductImageCreateSchema(
                product_id=product_id,
                display_order=index,
                is_primary=(index == 0)  # La première image est principale
            )

            try:
                result = await self.upload_and_create(file, schema, user_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Erreur upload image {file.filename}: {e}")
                continue

        return results

    def get_product_images(self, product_id: int) -> List[ProductImageSchema]:
        """Récupérer toutes les images d'un produit"""
        images = self.product_image_repo.get_by_product_id(product_id)
        return [ProductImageSchema.model_validate(img) for img in images]

    def delete_image(self, image_id: int, user_id: int) -> bool:
        """Supprimer une image (propriétaire du produit OU admin — T6)"""
        image = self.product_image_repo.get_by_id(image_id)
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image non trouvée"
            )

        # Autorisation via le produit rattaché.
        self._ensure_can_manage(image.product_id, user_id)

        # Supprimer les fichiers physiques
        self.file_service.delete_file(image.image_url)
        if image.thumbnail_url:
            self.file_service.delete_file(image.thumbnail_url)

        # Soft delete en base
        self.product_image_repo.update(image_id, is_deleted=True)

        logger.info(f"Image {image_id} supprimée")
        return True

    def set_primary_image(self, image_id: int, product_id: int, user_id: int) -> bool:
        """Définir une image comme principale (propriétaire du produit OU admin — T6)"""
        self._ensure_can_manage(product_id, user_id)
        self.product_image_repo.set_as_primary(image_id, product_id)
        logger.info(f"Image {image_id} définie comme principale pour produit {product_id}")
        return True

    def reorder_images(self, product_id: int, image_orders: dict, user_id: int) -> bool:
        """Réorganiser les images (propriétaire du produit OU admin — T6)"""
        self._ensure_can_manage(product_id, user_id)
        self.product_image_repo.reorder_images(image_orders)
        logger.info(f"Images du produit {product_id} réorganisées")
        return True