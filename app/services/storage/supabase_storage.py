# app/services/storage/supabase_storage.py
"""Stockage via Supabase Storage (bucket public), pour de la persistance gratuite.

API REST Supabase Storage (https://supabase.com/docs/guides/storage) :
- Upload  : POST   {url}/storage/v1/object/{bucket}/{path}   (header x-upsert pour écraser)
- Public  : GET    {url}/storage/v1/object/public/{bucket}/{path}
- Delete  : DELETE {url}/storage/v1/object/{bucket}/{path}

Auth via la clé `service_role` (jamais exposée au client mobile — backend only).
"""
from typing import Optional
from urllib.parse import quote

import httpx

from app.core.logger import logger


class SupabaseStorage:
    def __init__(self, supabase_url: str, service_key: str, bucket: str):
        self.base = supabase_url.rstrip("/")
        self.service_key = service_key
        self.bucket = bucket
        self._public_marker = f"/storage/v1/object/public/{bucket}/"

    def _headers(self, content_type: Optional[str] = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def save(self, data: bytes, dest_path: str, content_type: str) -> str:
        encoded = quote(dest_path)
        endpoint = f"{self.base}/storage/v1/object/{self.bucket}/{encoded}"
        headers = self._headers(content_type)
        headers["x-upsert"] = "true"  # écrase si le chemin existe déjà

        resp = httpx.post(endpoint, content=data, headers=headers, timeout=30.0)
        if resp.status_code not in (200, 201):
            logger.error(f"Upload Supabase échoué ({resp.status_code}): {resp.text}")
            raise RuntimeError(f"Supabase upload failed: {resp.status_code}")

        return f"{self.base}/storage/v1/object/public/{self.bucket}/{encoded}"

    def delete(self, url: str) -> bool:
        if not url or self._public_marker not in url:
            logger.warning(f"URL Supabase invalide pour suppression: {url}")
            return False

        path = url.split(self._public_marker, 1)[1]
        endpoint = f"{self.base}/storage/v1/object/{self.bucket}/{path}"
        try:
            resp = httpx.request("DELETE", endpoint, headers=self._headers(), timeout=30.0)
            if resp.status_code == 200:
                logger.info(f"Fichier Supabase supprimé: {path}")
                return True
            logger.warning(f"Suppression Supabase échouée ({resp.status_code}): {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Erreur suppression Supabase {url}: {e}")
            return False
