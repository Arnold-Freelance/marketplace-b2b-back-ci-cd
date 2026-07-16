"""
Conftest pytest : fixtures partagées.

- `valid_jwt` : factory de JWT signé avec le SECRET_KEY courant.
- `client` : TestClient FastAPI minimal pour tester les middlewares.

Note : on construit une app "test" minimale plutôt que d'importer toute
l'app de prod (qui dépend de la BD). Pour les tests d'endpoints réels,
ajouter une fixture DB SQLite en mémoire et override get_db.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

# Garantir que le package "app" est importable
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Fournir des valeurs minimales pour les variables d'env obligatoires
# AVANT d'importer settings (sinon Pydantic plante)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only-32chars")

from app.config.settings import settings  # noqa: E402
from app.api.deps import (  # noqa: E402
    get_current_user,
    get_optional_user,
    require_role,
)
from app.middleware.auth_middleware import AuthMiddleware  # noqa: E402
from app.middleware.response_middleware import ResponseWrappingMiddleware  # noqa: E402


@pytest.fixture
def make_jwt():
    """Factory : génère un JWT signé avec un user_id donné."""

    def _make(
        user_id: int = 42,
        user_type: str = "supplier",
        expired: bool = False,
        roles: list | None = None,
    ):
        now = datetime.now(timezone.utc)
        exp = now - timedelta(minutes=5) if expired else now + timedelta(minutes=30)
        if roles is None:
            roles = ["buyer", "supplier"] if user_type == "supplier" else [user_type]
        payload = {
            "user_id": str(user_id),
            "type": user_type,
            "roles": roles,
            "exp": exp,
            "iat": now,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return _make


@pytest.fixture
def app_with_middlewares():
    """Mini-app FastAPI avec auth + response middlewares pour tester en isolation.

    Depuis T2, `AuthMiddleware` ne bloque plus : il peuple seulement l'identité.
    La protection est portée par les dépendances de route :
    - `get_current_user` → 401 si anonyme (route protégée)
    - `get_optional_user` → identité optionnelle (route publique)
    """
    app = FastAPI()
    # Ordre : Auth interne (premier ajouté), Wrapping externe (dernier ajouté).
    app.add_middleware(AuthMiddleware)
    app.add_middleware(ResponseWrappingMiddleware)

    @app.get("/")
    def public_root():
        return {"hello": "world"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/v1/auth/login")
    def public_login():
        return {"login": "public"}

    # Route PUBLIQUE : identité optionnelle, jamais 401.
    @app.get("/public-catalogue")
    def public_catalogue(user_id=Depends(get_optional_user)):
        return {"public": True, "user_id": user_id}

    # Route PROTÉGÉE : exige un token valide via get_current_user.
    @app.get("/protected")
    def protected_endpoint(user_id: int = Depends(get_current_user)):  # noqa: ARG001
        return {"protected": True}

    @app.get("/protected-with-id")
    def protected_with_id(user_id: int = Depends(get_current_user)):
        return {"got_user": user_id}

    # Endpoint qui retourne déjà un ResponseBase
    @app.get("/already-wrapped")
    def already_wrapped():
        return {"success": True, "message": "deja wrap", "item": {"x": 1}}

    # Endpoint qui retourne une liste
    @app.get("/list-endpoint")
    def list_endpoint():
        return [{"id": 1}, {"id": 2}]

    return app


@pytest.fixture
def client(app_with_middlewares):
    return TestClient(app_with_middlewares)
