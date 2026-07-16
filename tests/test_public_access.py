"""Tests d'intégration T2 — accès public sélectif au frontoffice acheteur.

Vérifie sur l'app RÉELLE (SQLite en mémoire) que :
- les GET catalogue (produits, catégories) sont accessibles SANS token → 200 ;
- les écritures et le panier serveur restent protégés SANS token → 401.

C'est la garantie de non-régression du modèle « protection sélective » : si un
jour une route de lecture catalogue redevient protégée, ou qu'une écriture
devient publique, ces tests cassent.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient


@pytest.fixture
def api_client():
    """TestClient sur l'app réelle avec une base SQLite en mémoire."""
    from app.main_new import app
    from app.db.base import Base
    from app.api import deps

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def _get_db_override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[deps.get_db] = _get_db_override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(deps.get_db, None)
        Base.metadata.drop_all(bind=engine)


class TestPublicCatalogue:
    def test_list_products_is_public(self, api_client):
        r = api_client.get("/api/v1/products")
        assert r.status_code == 200

    def test_list_categories_is_public(self, api_client):
        r = api_client.get("/api/v1/categories")
        assert r.status_code == 200

    def test_featured_products_is_public(self, api_client):
        r = api_client.get("/api/v1/products/featured")
        assert r.status_code == 200

    def test_recent_products_is_public(self, api_client):
        r = api_client.get("/api/v1/products/recent")
        assert r.status_code == 200


class TestProtectedActions:
    def test_create_product_requires_auth(self, api_client):
        r = api_client.post("/api/v1/products", json={})
        assert r.status_code == 401

    def test_create_category_requires_auth(self, api_client):
        r = api_client.post("/api/v1/categories", json={})
        assert r.status_code == 401

    def test_get_cart_requires_auth(self, api_client):
        r = api_client.get("/api/v1/cart")
        assert r.status_code == 401

    def test_set_primary_image_requires_auth(self, api_client):
        """Écriture jadis non protégée (corrigée en T2)."""
        r = api_client.put("/api/v1/products/1/images/1/primary")
        assert r.status_code == 401

    def test_reorder_images_requires_auth(self, api_client):
        """Écriture jadis non protégée (corrigée en T2)."""
        r = api_client.put("/api/v1/products/1/images/order", json={"1": 0})
        assert r.status_code == 401
