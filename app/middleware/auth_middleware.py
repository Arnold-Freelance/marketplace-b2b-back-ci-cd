"""
Auth middleware — décode le JWT s'il est présent et expose l'identité dans
`request.state`, SANS jamais bloquer la requête.

Modèle « protection sélective » (finalisation v1, tâche T2) :
- Le middleware ne fait plus barrage global. Il se contente de *peupler*
  l'identité (`request.state.user_id` / `user_payload`) quand un token valide
  est fourni ; sinon il laisse `user_id = None` et laisse passer.
- La protection est désormais assurée **au niveau route** :
    * route publique  → aucune dépendance d'auth (catalogue, détail produit…)
    * route protégée  → `Depends(get_current_user)` qui renvoie 401 si anonyme
    * route à rôle    → guard dédié (cf. T5/T6)

Conséquence : un token présent mais invalide/expiré n'est plus rejeté par le
middleware ; la requête est traitée comme anonyme et c'est `get_current_user`
(ou le guard de rôle) qui renverra 401/403 si la route l'exige.
"""
import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config.settings import settings
from app.core.logger import logger


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Décode le JWT Bearer (si présent) et stocke l'identité dans `request.state`.

    `request.state.user_id` (int | None) et `request.state.user_payload`
    (dict | None) sont disponibles dans toutes les routes. Ne bloque jamais :
    la protection est déléguée aux dépendances de route.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Identité par défaut : anonyme. Les routes publiques peuvent lire
        # request.state.user_id (None) sans crash ; les routes protégées
        # exigent une valeur via get_current_user.
        request.state.user_id = None
        request.state.user_payload = None
        request.state.roles = []

        authorization = request.headers.get("Authorization")
        if authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                self._try_populate_identity(request, parts[1])
            else:
                logger.debug("Header Authorization mal formé — requête traitée en anonyme")

        return await call_next(request)

    @staticmethod
    def _try_populate_identity(request: Request, token: str) -> None:
        """Décode le token et pose l'identité ; silencieux si invalide/expiré."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except jwt.InvalidTokenError:
            # Couvre ExpiredSignatureError et tout token invalide.
            logger.debug("Token présent mais invalide/expiré — requête traitée en anonyme")
            return

        user_id_raw = payload.get("user_id")
        try:
            user_id = int(user_id_raw)
        except (TypeError, ValueError):
            logger.debug("Token sans user_id exploitable — requête traitée en anonyme")
            return

        if user_id <= 0:
            return

        request.state.user_id = user_id
        request.state.user_payload = payload
        roles = payload.get("roles")
        request.state.roles = list(roles) if isinstance(roles, list) else []
        logger.debug(
            f"Auth OK — user_id={user_id} roles={request.state.roles} path={request.url.path}"
        )
