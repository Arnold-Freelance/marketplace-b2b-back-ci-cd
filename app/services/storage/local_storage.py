# app/services/storage/local_storage.py
"""Stockage sur disque local. Les fichiers sont servis via /uploads (StaticFiles).

⚠️ Sur un hébergement à disque éphémère (Render free), les fichiers écrits ici
sont perdus à chaque redéploiement / réveil. Pour de la persistance, utiliser
le backend Supabase (STORAGE_BACKEND=supabase).
"""
from pathlib import Path

from app.core.logger import logger


class LocalStorage:
    URL_PREFIX = "/uploads"

    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = Path(base_dir)

    def save(self, data: bytes, dest_path: str, content_type: str) -> str:
        full = self.base_dir / dest_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return f"{self.URL_PREFIX}/{dest_path}"

    def delete(self, url: str) -> bool:
        if not url or not url.startswith(f"{self.URL_PREFIX}/"):
            logger.warning(f"URL locale invalide pour suppression: {url}")
            return False

        rel = url[len(self.URL_PREFIX) + 1:]
        path = self.base_dir / rel
        try:
            # Sécurité : empêcher de sortir du dossier de base (path traversal)
            if not str(path.resolve()).startswith(str(self.base_dir.resolve())):
                logger.error(f"Suppression hors du dossier uploads refusée: {path}")
                return False
            if not path.is_file():
                logger.warning(f"Fichier introuvable: {path}")
                return False
            path.unlink()
            logger.info(f"Fichier supprimé: {path}")
            return True
        except Exception as e:
            logger.error(f"Erreur suppression {url}: {e}")
            return False
