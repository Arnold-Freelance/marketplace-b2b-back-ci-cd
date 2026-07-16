# app/services/file_upload_service.py
"""
Service pour gérer l'upload et la gestion des fichiers (images, documents)
"""
import os
import uuid
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import shutil

from fastapi import UploadFile, HTTPException, status
from PIL import Image
import io

from app.config.settings import settings
from app.core.logger import logger
from app.services.storage import get_storage


class FileUploadService:
    """Service pour gérer l'upload de fichiers"""

    # Extensions autorisées
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx'}

    # Mapping extension -> (format PIL, content-type) pour l'encodage en mémoire
    _PIL_FORMATS = {
        '.jpg': ('JPEG', 'image/jpeg'),
        '.jpeg': ('JPEG', 'image/jpeg'),
        '.png': ('PNG', 'image/png'),
        '.gif': ('GIF', 'image/gif'),
        '.webp': ('WEBP', 'image/webp'),
    }

    # Tailles maximales (en bytes)
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB

    # Dimensions pour le redimensionnement des images
    THUMBNAIL_SIZE = (150, 150)
    MEDIUM_SIZE = (800, 800)
    LARGE_SIZE = (1920, 1920)

    def __init__(self, base_upload_dir: str = "uploads"):
        """
        Initialiser le service

        Args:
            base_upload_dir: Répertoire de base pour les uploads
        """
        self.base_upload_dir = Path(base_upload_dir)
        # Backend de stockage (local disque ou Supabase Storage selon settings)
        self.storage = get_storage()

    def _generate_unique_filename(self, original_filename: str) -> str:
        """
        Générer un nom de fichier unique

        Args:
            original_filename: Nom original du fichier

        Returns:
            Nom de fichier unique avec extension
        """
        # Extraire l'extension
        ext = Path(original_filename).suffix.lower()

        # Générer un nom unique avec timestamp et UUID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]

        return f"{timestamp}_{unique_id}{ext}"

    def _validate_file_size(self, file: UploadFile, max_size: int) -> None:
        """
        Valider la taille du fichier

        Args:
            file: Fichier uploadé
            max_size: Taille maximale autorisée en bytes

        Raises:
            HTTPException: Si le fichier est trop volumineux
        """
        # Lire la taille du fichier
        file.file.seek(0, 2)  # Aller à la fin
        file_size = file.file.tell()
        file.file.seek(0)  # Revenir au début

        if file_size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Le fichier est trop volumineux. Taille maximale: {max_size_mb:.1f} MB"
            )

    def _validate_image_extension(self, filename: str) -> None:
        """
        Valider l'extension d'une image

        Args:
            filename: Nom du fichier

        Raises:
            HTTPException: Si l'extension n'est pas autorisée
        """
        ext = Path(filename).suffix.lower()
        if ext not in self.ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extension non autorisée. Extensions acceptées: {', '.join(self.ALLOWED_IMAGE_EXTENSIONS)}"
            )

    def _validate_document_extension(self, filename: str) -> None:
        """
        Valider l'extension d'un document

        Args:
            filename: Nom du fichier

        Raises:
            HTTPException: Si l'extension n'est pas autorisée
        """
        ext = Path(filename).suffix.lower()
        if ext not in self.ALLOWED_DOCUMENT_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extension non autorisée. Extensions acceptées: {', '.join(self.ALLOWED_DOCUMENT_EXTENSIONS)}"
            )

    def _resize_image(self, image: Image.Image, max_size: tuple) -> Image.Image:
        """
        Redimensionner une image en conservant le ratio

        Args:
            image: Image PIL
            max_size: Dimensions maximales (largeur, hauteur)

        Returns:
            Image redimensionnée
        """
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        return image

    def _encode_image(self, image: Image.Image, ext: str) -> tuple[bytes, str]:
        """Encoder une image PIL en bytes selon son extension.

        Returns:
            (contenu binaire, content-type)
        """
        fmt, content_type = self._PIL_FORMATS.get(ext.lower(), ('JPEG', 'image/jpeg'))
        buffer = io.BytesIO()
        save_kwargs = {"optimize": True}
        if fmt in ("JPEG", "WEBP"):
            save_kwargs["quality"] = 90
        image.save(buffer, format=fmt, **save_kwargs)
        return buffer.getvalue(), content_type

    async def upload_product_image(
            self,
            file: UploadFile,
            create_thumbnail: bool = True
    ) -> dict:
        """
        Uploader une image de produit

        Args:
            file: Fichier image uploadé
            create_thumbnail: Créer une miniature

        Returns:
            Dict avec les URLs des images

        Raises:
            HTTPException: Si validation échoue
        """
        try:
            # Validations
            self._validate_image_extension(file.filename)
            self._validate_file_size(file, self.MAX_IMAGE_SIZE)

            # Générer un nom unique
            unique_filename = self._generate_unique_filename(file.filename)
            ext = Path(unique_filename).suffix

            # Lire l'image
            contents = await file.read()
            image = Image.open(io.BytesIO(contents))

            # Convertir en RGB si nécessaire (pour les PNG avec transparence)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background

            # Redimensionner et sauvegarder l'image principale via le backend de stockage
            resized_image = self._resize_image(image.copy(), self.LARGE_SIZE)
            image_data, content_type = self._encode_image(resized_image, ext)
            original_url = self.storage.save(
                image_data, f"products/images/{unique_filename}", content_type
            )

            result = {
                "original": original_url,
                "thumbnail": None
            }

            # Créer une miniature si demandé
            if create_thumbnail:
                thumbnail_filename = f"thumb_{unique_filename}"
                thumbnail = self._resize_image(image.copy(), self.THUMBNAIL_SIZE)
                thumb_data, thumb_ct = self._encode_image(thumbnail, ext)
                result["thumbnail"] = self.storage.save(
                    thumb_data, f"products/thumbnails/{thumbnail_filename}", thumb_ct
                )

            logger.info(f"Image uploadée avec succès: {unique_filename}")
            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erreur lors de l'upload de l'image: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de l'upload de l'image"
            )

    # ================================================
    # MÉTHODES DE SUPPRESSION
    # ================================================

    def delete_file(self, file_url: str) -> bool:
        """
        Supprimer un fichier via le backend de stockage (local ou Supabase).

        Args:
            file_url: URL publique du fichier (ex: /uploads/products/images/xxx.jpg
                      ou une URL Supabase absolue)

        Returns:
            True si supprimé avec succès, False sinon
        """
        if not file_url:
            return False
        return self.storage.delete(file_url)

    def delete_multiple_files(self, file_urls: list) -> int:
        """
        Supprimer plusieurs fichiers

        Args:
            file_urls: Liste d'URLs de fichiers

        Returns:
            Nombre de fichiers supprimés avec succès
        """
        deleted_count = 0

        for file_url in file_urls:
            if self.delete_file(file_url):
                deleted_count += 1

        logger.info(f"{deleted_count}/{len(file_urls)} fichiers supprimés")
        return deleted_count

    def delete_product_images(self, image_url: str, thumbnail_url: str = None) -> bool:
        """
        Supprimer une image de produit et sa miniature

        Args:
            image_url: URL de l'image originale
            thumbnail_url: URL de la miniature (optionnel)

        Returns:
            True si au moins un fichier a été supprimé
        """
        success = False

        # Supprimer l'image originale
        if image_url:
            if self.delete_file(image_url):
                success = True

        # Supprimer la miniature
        if thumbnail_url:
            if self.delete_file(thumbnail_url):
                success = True

        return success