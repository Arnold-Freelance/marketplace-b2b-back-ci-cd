"""Tests T6 — séparation stricte des accès (niveau route).

Monte les vrais routeurs derrière `AuthMiddleware` et vérifie que les garde-fous
de rôle bloquent effectivement :
- catégories (écritures) → réservé admin ;
- `/supplier/dashboard` → réservé supplier ;
- produits (écritures) → réservé supplier/admin.

On teste les rejets critiques (buyer → 403, anonyme → 401), stoppés au guard
avant tout accès aux données. Le chemin positif (bon rôle → 200) est couvert par
`test_user_roles.py` (comportement générique de `require_role`).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth_middleware import AuthMiddleware
from app.api.v1.categories import router as categories_router
from app.api.v1.supplier import router as supplier_router
from app.api.v1.products import router as products_router


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(categories_router)
    app.include_router(supplier_router)
    app.include_router(products_router)
    # Ne pas propager les 500 (au cas où un guard passant toucherait la BD absente).
    return TestClient(app, raise_server_exceptions=False)


CATEGORY_WRITES = [
    ("post", "/api/v1/categories"),
    ("put", "/api/v1/categories/1"),
    ("delete", "/api/v1/categories/1"),
]


def test_categories_write_forbidden_for_buyer(client, make_jwt):
    token = make_jwt(user_id=2, roles=["buyer"])
    for method, url in CATEGORY_WRITES:
        r = client.request(
            method, url,
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Cat", "slug": "cat"},
        )
        assert r.status_code == 403, f"{method} {url} → {r.status_code}"


def test_categories_write_unauthenticated_401(client):
    for method, url in CATEGORY_WRITES:
        r = client.request(method, url, json={"name": "Cat", "slug": "cat"})
        assert r.status_code == 401, f"{method} {url} → {r.status_code}"


def test_categories_write_forbidden_for_supplier(client, make_jwt):
    # Un supplier (buyer+supplier) ne doit PAS gérer les catégories.
    token = make_jwt(user_id=3, roles=["buyer", "supplier"])
    r = client.post(
        "/api/v1/categories",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Cat", "slug": "cat"},
    )
    assert r.status_code == 403


def test_supplier_dashboard_forbidden_for_buyer(client, make_jwt):
    token = make_jwt(user_id=2, roles=["buyer"])
    r = client.get(
        "/api/v1/supplier/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_supplier_dashboard_unauthenticated_401(client):
    assert client.get("/api/v1/supplier/dashboard").status_code == 401


def test_product_create_forbidden_for_buyer(client, make_jwt):
    token = make_jwt(user_id=2, roles=["buyer"])
    r = client.post(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "P", "slug": "p", "category_id": 1, "price": 10},
    )
    assert r.status_code == 403


def test_product_create_unauthenticated_401(client):
    r = client.post(
        "/api/v1/products",
        json={"name": "P", "slug": "p", "category_id": 1, "price": 10},
    )
    assert r.status_code == 401
