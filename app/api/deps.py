"""
Dépendances FastAPI partagées.

- `get_db`        : session SQLAlchemy.
- `get_current_user` : user_id de l'utilisateur authentifié. Lit
  `request.state.user_id` posé par `AuthMiddleware` — pas de re-décodage du
  JWT, c'est juste un alias pratique pour les routes.
"""
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(request: Request) -> int:
    """
    Retourne l'user_id authentifié, déjà extrait du JWT par AuthMiddleware.

    Si appelée sur une route publique (whitelistée dans le middleware) où
    aucun token n'a été fourni, `state.user_id` vaut None et on lève 401.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        # Anonyme sur une route protégée → 401. Depuis T2, c'est cette
        # dépendance (et non le middleware) qui assure la protection.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


async def get_optional_user(request: Request) -> Optional[int]:
    """
    Retourne l'user_id si un token valide a été fourni, sinon `None`.

    À utiliser sur les routes **publiques** qui veulent connaître l'utilisateur
    quand il est connecté (personnalisation) sans jamais l'exiger : catalogue,
    détail produit, profil public fournisseur… Ne lève jamais 401.
    """
    return getattr(request.state, "user_id", None)


def get_current_roles(request: Request) -> list[str]:
    """Rôles de l'utilisateur courant (posés par AuthMiddleware depuis le JWT)."""
    roles = getattr(request.state, "roles", None)
    return list(roles) if isinstance(roles, list) else []


def require_role(*allowed_roles: str):
    """
    Fabrique une dépendance qui exige la **présence** d'au moins un des rôles
    donnés (T5). 401 si anonyme, 403 si authentifié sans le rôle requis.

    Usage :
        @router.get("/dashboard")
        async def dashboard(user_id: int = Depends(require_role("supplier"))):
            ...

    Retourne l'user_id (pratique pour l'utiliser directement dans la route).
    """
    allowed = set(allowed_roles)

    async def _guard(request: Request) -> int:
        user_id = getattr(request.state, "user_id", None)
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Non authentifié",
                headers={"WWW-Authenticate": "Bearer"},
            )
        roles = get_current_roles(request)
        if allowed.isdisjoint(roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès réservé au(x) rôle(s) : {', '.join(sorted(allowed))}",
            )
        return user_id

    return _guard
