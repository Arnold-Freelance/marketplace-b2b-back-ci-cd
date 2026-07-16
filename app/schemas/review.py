"""
Schémas pour les évaluations et avis
"""
from typing import Optional, Dict
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from app.schemas.schema_base import SchemaBase


class ReviewSchema(SchemaBase):
    """Schéma pour un avis"""
    id: Optional[int] = None
    order_id: Optional[int] = None
    reviewer_id: Optional[int] = None
    reviewed_id: Optional[int] = None
    product_id: Optional[int] = None

    # Évaluation
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = None
    comment: Optional[str] = None

    # Critères détaillés
    quality_rating: Optional[int] = Field(None, ge=1, le=5)
    delivery_rating: Optional[int] = Field(None, ge=1, le=5)
    service_rating: Optional[int] = Field(None, ge=1, le=5)
    value_rating: Optional[int] = Field(None, ge=1, le=5)

    # Métadonnées
    is_verified: bool = False
    is_public: bool = True

    # Réponse du fournisseur
    supplier_response: Optional[str] = None
    supplier_response_at: Optional[str] = None

    # Utilité
    helpful_count: int = 0
    not_helpful_count: int = 0

    # Informations enrichies
    reviewer_name: Optional[str] = None
    reviewer_avatar: Optional[str] = None
    product_name: Optional[str] = None
    product_image: Optional[str] = None
    reviewed_user_name: Optional[str] = None  # Nom du fournisseur

    # Moyennes calculées
    average_detailed_rating: Optional[float] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CreateReviewSchema(BaseModel):
    """Schéma pour créer un avis"""
    order_id: int = Field(..., gt=0)
    product_id: Optional[int] = Field(None, gt=0)

    rating: int = Field(..., ge=1, le=5, description="Note globale de 1 à 5")
    title: Optional[str] = Field(None, max_length=255, description="Titre de l'avis")
    comment: Optional[str] = Field(None, max_length=2000, description="Commentaire détaillé")

    # Critères détaillés (optionnels)
    quality_rating: Optional[int] = Field(None, ge=1, le=5)
    delivery_rating: Optional[int] = Field(None, ge=1, le=5)
    service_rating: Optional[int] = Field(None, ge=1, le=5)
    value_rating: Optional[int] = Field(None, ge=1, le=5)

    is_public: bool = Field(default=True, description="Avis public ou privé")

    @field_validator('comment')
    @classmethod
    def validate_comment(cls, v):
        """Valider que le commentaire n'est pas vide si fourni"""
        if v and not v.strip():
            raise ValueError("Le commentaire ne peut pas être vide")
        return v


class UpdateReviewSchema(BaseModel):
    """Schéma pour mettre à jour un avis"""
    review_id: int = Field(..., gt=0)

    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    comment: Optional[str] = Field(None, max_length=2000)

    quality_rating: Optional[int] = Field(None, ge=1, le=5)
    delivery_rating: Optional[int] = Field(None, ge=1, le=5)
    service_rating: Optional[int] = Field(None, ge=1, le=5)
    value_rating: Optional[int] = Field(None, ge=1, le=5)

    is_public: Optional[bool] = None


class SupplierResponseSchema(BaseModel):
    """Schéma pour la réponse du fournisseur"""
    review_id: int = Field(..., gt=0)
    response: str = Field(..., min_length=10, max_length=1000)


class ReviewHelpfulVoteSchema(BaseModel):
    """Schéma pour voter sur l'utilité d'un avis"""
    review_id: int = Field(..., gt=0)
    is_helpful: bool = Field(..., description="True = utile, False = pas utile")


class ReviewStatisticsSchema(BaseModel):
    """Schéma pour les statistiques d'avis"""
    total_reviews: int = 0
    average_rating: float = 0.0
    rating_distribution: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    # Moyennes des critères détaillés
    average_quality_rating: Optional[float] = None
    average_delivery_rating: Optional[float] = None
    average_service_rating: Optional[float] = None
    average_value_rating: Optional[float] = None

    # Pourcentages
    percentage_5_stars: float = 0.0
    percentage_4_stars: float = 0.0
    percentage_3_stars: float = 0.0
    percentage_2_stars: float = 0.0
    percentage_1_star: float = 0.0

    # Avis vérifiés
    verified_reviews_count: int = 0
    verified_percentage: float = 0.0