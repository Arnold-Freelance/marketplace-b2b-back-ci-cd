# ================================================
# app/schemas/reputation.py
# ================================================
"""
Schémas pour la réputation des utilisateurs/produits
"""
from typing import Optional, Dict
from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.schema_base import SchemaBase


class UserReputationSchema(BaseModel):
    """Schéma pour la réputation d'un utilisateur"""
    user_id: int
    user_name: str

    # Statistiques globales
    total_reviews: int = 0
    average_rating: float = 0.0

    # Distribution des notes
    rating_distribution: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    # Badges/Niveau
    reputation_level: str = "Nouveau"  # Nouveau, Bronze, Argent, Or, Platine
    is_top_rated: bool = False

    # Statistiques de vente (pour fournisseurs)
    total_orders: Optional[int] = 0
    completed_orders: Optional[int] = 0
    completion_rate: Optional[float] = 0.0

    # Temps de réponse moyen
    average_response_time: Optional[str] = None


class ProductReputationSchema(BaseModel):
    """Schéma pour la réputation d'un produit"""
    product_id: int
    product_name: str

    # Statistiques d'avis
    total_reviews: int = 0
    average_rating: float = 0.0
    rating_distribution: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    # Critères détaillés
    average_quality_rating: Optional[float] = None
    average_delivery_rating: Optional[float] = None
    average_service_rating: Optional[float] = None
    average_value_rating: Optional[float] = None

    # Recommandation
    recommendation_percentage: float = 0.0  # % d'avis 4-5 étoiles

    # Popularité
    favorites_count: int = 0
    views_count: int = 0
    orders_count: int = 0