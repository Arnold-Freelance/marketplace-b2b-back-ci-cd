# main.py
"""
Application FastAPI avec gestion centralisée des exceptions
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.middleware.exception_middleware import (
    register_exception_handlers,
    RequestLoggingMiddleware
)
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.response_middleware import ResponseWrappingMiddleware
from app.config.settings import settings
from app.core.logger import logger
from app.api.v1 import (
    addresses,
    auth,
    products,
    categories,
    cart,
    orders,
    reviews,
    wishlist,
    product_images,
    messaging,
    notifications,
    websocket,
    payments,
    supplier,
    users,
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire du cycle de vie de l'application"""
    # Démarrage
    logger.info("🚀 Démarrage de l'application...")

    # Le schéma de base est désormais géré par Alembic (migrations), plus par
    # create_all() — qui ne modifiait pas l'existant et causait des dérives.
    # Pour (re)construire/mettre à jour la base : `alembic upgrade head`.

    yield

    # Arrêt
    logger.info("🛑 Arrêt de l'application...")


# Créer l'application
app = FastAPI(
    title="API Gestion de Catégories",
    description="API RESTful avec gestion centralisée des exceptions",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# ==================== MIDDLEWARES ====================
# Starlette execute les middlewares dans l'ordre INVERSE d'ajout :
# le DERNIER ajouté est le PLUS EXTERNE (premier appele a l'entree de la requete).
#
# Flux entree (request)  : Logging -> CORS -> GZip -> ResponseWrapping -> Auth -> route
# Flux sortie (response) : route -> Auth -> ResponseWrapping -> GZip -> CORS -> Logging

# 1. Auth (le plus interne, proche routes) : decode JWT, expose user_id dans request.state
app.add_middleware(AuthMiddleware)

# 2. Response wrapping : enrobe automatiquement les reponses JSON non-ResponseBase
app.add_middleware(ResponseWrappingMiddleware)

# 3. Compression GZIP (apres le wrapping, pour compresser le body deja enrobe)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 4. CORS (externe, gere les preflights avant tout traitement applicatif)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # configurable via CORS_ORIGINS (.env)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Logging (le plus externe, mesure le temps total)
app.add_middleware(RequestLoggingMiddleware)

# ==================== GESTIONNAIRES D'EXCEPTIONS ====================

# Enregistrer tous les gestionnaires d'exceptions
# C'est ici que toutes les exceptions sont capturées et converties en réponses HTTP
register_exception_handlers(app)

# ==================== FICHIERS STATIQUES (uploads) ====================
# Sert les images produit. /uploads est whitelisté dans AuthMiddleware.
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ==================== ROUTES ====================

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(reviews.router)
app.include_router(wishlist.router)
app.include_router(product_images.router)
app.include_router(messaging.router)
app.include_router(notifications.router)
app.include_router(websocket.router)
app.include_router(payments.router)
app.include_router(supplier.router)
app.include_router(supplier.public_router)
app.include_router(users.router)
app.include_router(addresses.router)




# ==================== ENDPOINTS DE BASE ====================

@app.get("/", tags=["Health"])
async def root():
    """Point d'entrée de l'API"""
    return {
        "message": "API Gestion de Catégories v2",
        "status": "running",
        "version": "2.0.0",
        "docs": "/api/docs",
        "features": [
            "Gestion centralisée des exceptions",
            "Validation multi-niveaux",
            "Service générique CRUD",
            "Logging structuré"
        ]
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Vérification de l'état de santé de l'API"""
    try:
        # Tester la connexion à la BD
        from sqlalchemy import text
        from app.db.session import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception as e:
        logger.error(f"Health check BD échoué: {str(e)}")
        db_status = "disconnected"

    return {
        "status": "healthy",
        "database": db_status,
        "version": "2.0.0"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )