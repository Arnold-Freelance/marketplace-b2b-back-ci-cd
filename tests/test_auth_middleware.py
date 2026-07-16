"""Tests du AuthMiddleware (modèle « protection sélective » — T2).

Depuis T2, le middleware ne bloque plus : il peuple seulement l'identité dans
`request.state`. La protection est portée par les dépendances de route
(`get_current_user` = 401 si anonyme, `get_optional_user` = identité optionnelle).
"""


class TestPublicRoutes:
    def test_root_is_public(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_health_is_public(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_auth_endpoints_are_public(self, client):
        r = client.get("/api/v1/auth/login")
        assert r.status_code == 200

    def test_public_catalogue_without_token_is_anonymous(self, client):
        """Route publique sans token → 200, identité None (pas de 401)."""
        r = client.get("/public-catalogue")
        assert r.status_code == 200
        assert r.json()["item"]["public"] is True
        assert r.json()["item"].get("user_id") is None

    def test_public_catalogue_with_token_exposes_identity(self, client, make_jwt):
        """Route publique avec token valide → identité disponible (personnalisation)."""
        token = make_jwt(user_id=7)
        r = client.get("/public-catalogue", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["item"]["user_id"] == 7

    def test_public_catalogue_ignores_invalid_token(self, client):
        """Un token invalide sur une route publique ne bloque pas → anonyme."""
        r = client.get(
            "/public-catalogue",
            headers={"Authorization": "Bearer not.a.jwt"},
        )
        assert r.status_code == 200
        assert r.json()["item"].get("user_id") is None


class TestProtectedRoutes:
    def test_protected_without_token_returns_401(self, client):
        r = client.get("/protected")
        assert r.status_code == 401

    def test_protected_with_invalid_format_returns_401(self, client):
        """Header mal formé → traité en anonyme → get_current_user renvoie 401."""
        r = client.get("/protected", headers={"Authorization": "Token abc"})
        assert r.status_code == 401

    def test_protected_with_invalid_token_returns_401(self, client):
        r = client.get("/protected", headers={"Authorization": "Bearer invalid.jwt.token"})
        assert r.status_code == 401

    def test_protected_with_expired_token_returns_401(self, client, make_jwt):
        token = make_jwt(user_id=1, expired=True)
        r = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_protected_with_valid_token_returns_200(self, client, make_jwt):
        token = make_jwt(user_id=42)
        r = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

    def test_state_user_id_exposed_to_endpoint(self, client, make_jwt):
        """Le middleware doit poser request.state.user_id pour la route."""
        token = make_jwt(user_id=99)
        r = client.get("/protected-with-id", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["item"]["got_user"] == 99
