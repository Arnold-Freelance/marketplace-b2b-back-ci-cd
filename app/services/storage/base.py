# app/services/storage/base.py
"""Abstraction de stockage de fichiers : disque local (dev) ou Supabase Storage (prod)."""
from typing import Optional, Protocol


class StorageBackend(Protocol):
    """Contrat commun à tous les backends de stockage."""

    def save(self, data: bytes, dest_path: str, content_type: str) -> str:
        """Persiste `data` à l'emplacement logique `dest_path`
        (ex: 'products/images/x.jpg') et retourne son URL publique."""
        ...

    def delete(self, url: str) -> bool:
        """Supprime le fichier désigné par son URL publique. True si supprimé."""
        ...
