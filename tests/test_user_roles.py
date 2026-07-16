"""Tests T5 — rôles multiples.

Couvre la chaîne complète des rôles :
- `AuthService.default_roles_for` : attribution par défaut (supplier ⇒ +buyer).
- `UserEntity.role_names` : fallback défensif quand la table user_roles est vide.
- `AuthMiddleware` : propagation des rôles du JWT vers `request.state.roles`.
- `require_role` : 401 anonyme, 403 rôle manquant, 200 rôle présent.

Le test d'intégration de la migration Postgres (données existantes migrées) a été
vérifié séparément sur une base jetable ; ici on couvre la logique applicative,
rejouable en CI sur SQLite.
"""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_roles, require_role
from app.middleware.auth_middleware import AuthMiddleware
from app.services.auth_service import AuthService


# --------------------------------------------------------------------------- #
# Logique pure : attribution des rôles par défaut
# --------------------------------------------------------------------------- #
def test_default_roles_for_supplier_includes_buyer():
    """Un vendeur est aussi acheteur."""
    assert AuthService.default_roles_for("supplier") == ["buyer", "supplier"]


def test_default_roles_for_buyer():
    assert AuthService.default_roles_for("buyer") == ["buyer"]


def test_default_roles_for_admin():
    assert AuthService.default_roles_for("admin") == ["admin"]


# --------------------------------------------------------------------------- #
# Fallback role_names sur l'entité (compte non encore migré → table vide)
# --------------------------------------------------------------------------- #
def test_role_names_fallback_supplier_adds_buyer():
    from app.core.enums import UserType
    from app.models.user_entity import UserEntity

    user = UserEntity(user_type=UserType.supplier)  # aucune ligne user_roles
    assert user.role_names == ["buyer", "supplier"]


def test_role_names_fallback_buyer():
    from app.core.enums import UserType
    from app.models.user_entity import UserEntity

    user = UserEntity(user_type=UserType.buyer)
    assert user.role_names == ["buyer"]


# --------------------------------------------------------------------------- #
# Guard require_role + propagation middleware, testés via une mini-app
# --------------------------------------------------------------------------- #
def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    @app.get("/whoami")
    def whoami(roles=Depends(get_current_roles)):
        return {"roles": roles}

    @app.get("/supplier-only")
    def supplier_only(user_id: int = Depends(require_role("supplier"))):
        return {"ok": True, "user_id": user_id}

    @app.get("/admin-only")
    def admin_only(user_id: int = Depends(require_role("admin"))):
        return {"ok": True}

    return app


def test_middleware_propagates_roles(make_jwt):
    client = TestClient(_make_app())
    token = make_jwt(user_id=7, roles=["buyer", "supplier"])
    resp = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert sorted(resp.json()["roles"]) == ["buyer", "supplier"]


def test_anonymous_roles_empty():
    client = TestClient(_make_app())
    resp = client.get("/whoami")
    assert resp.status_code == 200
    assert resp.json()["roles"] == []


def test_require_role_401_when_anonymous():
    client = TestClient(_make_app())
    resp = client.get("/supplier-only")
    assert resp.status_code == 401


def test_require_role_403_when_role_missing(make_jwt):
    client = TestClient(_make_app())
    token = make_jwt(user_id=8, roles=["buyer"])  # pas supplier
    resp = client.get("/supplier-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_require_role_200_when_role_present(make_jwt):
    client = TestClient(_make_app())
    token = make_jwt(user_id=9, roles=["buyer", "supplier"])
    resp = client.get("/supplier-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == 9


def test_require_admin_forbidden_for_supplier(make_jwt):
    """Un supplier (même + buyer) ne doit PAS accéder à une route admin."""
    client = TestClient(_make_app())
    token = make_jwt(user_id=10, roles=["buyer", "supplier"])
    resp = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_require_admin_ok_for_admin(make_jwt):
    client = TestClient(_make_app())
    token = make_jwt(user_id=1, roles=["admin"])
    resp = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
