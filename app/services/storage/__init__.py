# app/services/storage/__init__.py
"""Sélection du backend de stockage selon `settings.STORAGE_BACKEND`.

- "local"    : disque (dev / tests). Défaut.
- "supabase" : Supabase Storage (prod Render — persistant).
"""
from functools import lru_cache

from app.config.settings import settings
from app.core.logger import logger
from app.services.storage.base import StorageBackend
from app.services.storage.local_storage import LocalStorage
from app.services.storage.supabase_storage import SupabaseStorage

__all__ = ["get_storage", "StorageBackend"]


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    backend = (settings.STORAGE_BACKEND or "local").lower()

    if backend == "supabase":
        if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY):
            raise RuntimeError(
                "STORAGE_BACKEND=supabase mais SUPABASE_URL / SUPABASE_SERVICE_KEY manquants"
            )
        logger.info("Stockage fichiers: Supabase Storage (bucket=%s)", settings.SUPABASE_BUCKET)
        return SupabaseStorage(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY,
            settings.SUPABASE_BUCKET,
        )

    logger.info("Stockage fichiers: disque local (%s/)", settings.UPLOAD_DIR)
    return LocalStorage(settings.UPLOAD_DIR)
