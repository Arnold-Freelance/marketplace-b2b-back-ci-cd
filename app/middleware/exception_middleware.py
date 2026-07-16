# app/middleware/exception_middleware.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.core.exceptions import (
    BaseAppException,
    ValidationError,
    NotFoundError,
    DuplicateError,
    BusinessRuleError,
    DatabaseError,
    UnauthorizedError,
    ForbiddenError
)
from app.core.logger import logger

# Mapping Exception → HTTP Status Code
EXCEPTION_STATUS_MAP = {
    ValidationError: status.HTTP_400_BAD_REQUEST,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    DuplicateError: status.HTTP_409_CONFLICT,
    BusinessRuleError: status.HTTP_400_BAD_REQUEST,
    DatabaseError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    UnauthorizedError: status.HTTP_401_UNAUTHORIZED,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
}


def get_status_code(exception: Exception) -> int:
    """Déterminer le code HTTP pour une exception"""
    for exc_class, status_code in EXCEPTION_STATUS_MAP.items():
        if isinstance(exception, exc_class):
            return status_code
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def register_exception_handlers(app):
    """
    Enregistrer les gestionnaires d'exceptions centralisés

    Toutes les exceptions sont capturées ici et converties en réponses HTTP
    """

    @app.exception_handler(BaseAppException)
    async def base_app_exception_handler(request: Request, exc: BaseAppException):
        """
        Gestionnaire principal pour toutes nos exceptions personnalisées

        Les services lèvent des exceptions, ce middleware les convertit en réponses HTTP
        """
        status_code = get_status_code(exc)

        # Logger selon la sévérité
        if status_code >= 500:
            logger.error(f"Erreur serveur: {exc.message}", exc_info=True)
        elif status_code >= 400:
            logger.warning(f"Erreur client: {exc.message}")
        else:
            logger.info(f"Exception: {exc.message}")

        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "message": exc.message,
                "code": exc.code,
                "path": str(request.url.path)
            }
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        """Gestionnaire spécifique pour les erreurs de validation"""
        logger.warning(f"Validation échouée: {exc.message}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": "Erreur de validation",
                "errors": [exc.message],
                "code": "VALIDATION_ERROR"
            }
        )

    # @app.exception_handler(NotFoundError)
    # async def not_found_handler(request: Request, exc: NotFoundError):
    #     """Gestionnaire pour les ressources non trouvées"""
    #     logger.info(f"Ressource non trouvée: {exc.message}")
    #
    #     return JSONResponse(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         content={
    #             "success": False,
    #             "message": exc.message,
    #             "code": "NOT_FOUND"
    #         }
    #     )

    @app.exception_handler(BusinessRuleError)
    async def business_rule_handler(request: Request, exc: BusinessRuleError):
        """Gestionnaire pour les violations de règles métier"""
        logger.warning(f"Règle métier violée: {exc.message}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": exc.message,
                "code": "BUSINESS_RULE_VIOLATION"
            }
        )

    @app.exception_handler(RequestValidationError)
    async def pydantic_validation_handler(request: Request, exc: RequestValidationError):
        """
        Gestionnaire pour les erreurs de validation Pydantic

        Convertit les erreurs Pydantic en format lisible
        """
        errors = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            message = error["msg"]
            errors.append(f"{field}: {message}")
        logger.error(f"Validation errors: {exc.errors()}")
        logger.warning(f"Validation Pydantic échouée: {errors}")

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "message": "Les données fournies ne sont pas valides",
                "errors": errors,
                "code": "VALIDATION_ERROR"
            }
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        """Gestionnaire pour les erreurs d'intégrité de base de données"""
        logger.error(f"Erreur d'intégrité BD: {str(exc.orig)}")

        # Parser le message pour donner un retour plus clair
        message = "Erreur d'intégrité des données"
        if "unique constraint" in str(exc.orig).lower():
            message = "Cette valeur existe déjà dans la base de données"
        elif "foreign key" in str(exc.orig).lower():
            message = "Référence invalide vers une autre ressource"
        elif "not null" in str(exc.orig).lower():
            message = "Un champ obligatoire est manquant"

        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "message": message,
                "code": "INTEGRITY_ERROR"
            }
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
        """Gestionnaire pour les erreurs SQLAlchemy non gérées"""
        logger.error(f"Erreur SQLAlchemy: {str(exc)}", exc_info=True)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "Erreur interne de base de données",
                "code": "DATABASE_ERROR"
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """
        Gestionnaire catch-all pour toutes les exceptions non gérées

        IMPORTANT: À utiliser en dernier recours uniquement
        """
        logger.exception(f"Exception non gérée: {str(exc)}")

        # En production, ne pas exposer les détails de l'erreur
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "Une erreur interne est survenue",
                "code": "INTERNAL_SERVER_ERROR"
            }
        )


# ==================== MIDDLEWARE POUR LOGGER LES REQUÊTES ====================

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware pour logger toutes les requêtes HTTP"""

    # Routes à ne pas logger en détail
    SKIP_PATHS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next):
        # Skip logging pour certaines routes statiques
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # Démarrer le chrono
        start_time = time.time()

        # Logger la requête entrante
        logger.info(f"→ {request.method} {request.url.path}")

        # Traiter la requête
        try:
            response = await call_next(request)

            # Calculer la durée
            duration = time.time() - start_time

            # Logger la réponse
            log_level = "info" if response.status_code < 400 else "warning"
            getattr(logger, log_level)(
                f"← {request.method} {request.url.path} "
                f"[{response.status_code}] {duration:.3f}s"
            )

            # Ajouter les headers de performance
            response.headers["X-Process-Time"] = str(duration)

            return response

        except Exception as exc:
            duration = time.time() - start_time
            logger.error(
                f"✗ {request.method} {request.url.path} "
                f"[ERROR] {duration:.3f}s - {str(exc)}"
            )
            raise