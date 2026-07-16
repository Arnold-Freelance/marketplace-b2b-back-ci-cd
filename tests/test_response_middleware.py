"""Tests du ResponseWrappingMiddleware."""


class TestResponseWrapping:
    def test_dict_response_is_wrapped(self, client):
        r = client.get("/")  # retourne {"hello": "world"}
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["message"]
        assert body["item"] == {"hello": "world"}

    def test_list_response_is_wrapped_as_items(self, client):
        r = client.get("/list-endpoint")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["items"] == [{"id": 1}, {"id": 2}]
        assert body["total"] == 2

    def test_already_wrapped_response_passes_through(self, client):
        """Si l'endpoint retourne déjà un ResponseBase, ne pas re-wrapper."""
        r = client.get("/already-wrapped")
        assert r.status_code == 200
        body = r.json()
        assert body == {"success": True, "message": "deja wrap", "item": {"x": 1}}

    def test_401_error_is_not_wrapped(self, client):
        """Les erreurs (4xx/5xx) ne doivent PAS passer par le wrapping succès.

        Depuis T2, le 401 provient de la dépendance `get_current_user`
        (HTTPException) et non plus du middleware. Le point clé du test reste :
        une erreur n'est jamais enrobée dans l'enveloppe `{success, item}`.
        """
        r = client.get("/protected")  # 401 via get_current_user
        assert r.status_code == 401
        body = r.json()
        # Pas d'enveloppe succès : ni success=True, ni item.
        assert body.get("success") is not True
        assert "item" not in body
