"""
Décorateur @transactional pour les méthodes de service.

Inspiré du `@Transactional` Spring Boot. Garantit commit-en-succès /
rollback-en-erreur pour un bloc de logique métier.

Convention : le service doit avoir un attribut `db` (Session SQLAlchemy)
ou un repository avec un attribut `db`. Sinon, lève RuntimeError au
premier appel.

Exemple :
    class ProductService:
        def __init__(self, product_repo, ...):
            self.product_repo = product_repo
            self.db = product_repo.db  # nécessaire pour @transactional

        @transactional
        def create(self, data, user_id):
            product = self.product_repo.create(...)  # repo en autocommit=False
            self.audit_repo.create(...)              # idem
            return ResponseBase(...)
            # commit automatique en sortie si pas d'exception
            # rollback automatique si exception
"""
import functools
from typing import Callable

from app.core.logger import logger


def _get_session(service):
    """Récupère la Session SQLAlchemy depuis le service."""
    db = getattr(service, "db", None)
    if db is None:
        # Essayer via le premier repository trouvé
        for attr in vars(service).values():
            inner_db = getattr(attr, "db", None)
            if inner_db is not None:
                return inner_db
        raise RuntimeError(
            "@transactional : le service doit exposer une Session SQLAlchemy "
            "via self.db ou via un repository avec self.repo.db"
        )
    return db


def transactional(func: Callable) -> Callable:
    """
    Décorateur de méthode de service.

    Wrappe l'appel dans un try/except :
    - succès → db.commit()
    - exception → db.rollback() puis re-raise
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        db = _get_session(self)
        try:
            result = func(self, *args, **kwargs)
            db.commit()
            return result
        except Exception:
            db.rollback()
            logger.exception(
                f"@transactional rollback : {self.__class__.__name__}.{func.__name__}"
            )
            raise

    return wrapper
