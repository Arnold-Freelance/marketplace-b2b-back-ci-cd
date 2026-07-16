# ================================================
# app/repositories/review_repo.py
# ================================================
"""
Repositories pour les avis
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from app.models.review_entity import ReviewEntity, ReviewHelpfulVoteEntity
from app.repositories.base import BaseRepository
from app.schemas.review import ReviewStatisticsSchema


class ReviewRepository(BaseRepository):
    """Repository pour les avis"""

    def __init__(self, db: Session):
        super().__init__(db, ReviewEntity)

    def get_by_order_and_reviewer(
            self,
            order_id: int,
            reviewer_id: int,
            reviewed_id: int
    ) -> Optional[ReviewEntity]:
        """Récupérer un avis par commande et reviewer"""
        return (
            self.db.query(ReviewEntity)
            .filter(
                ReviewEntity.order_id == order_id,
                ReviewEntity.reviewer_id == reviewer_id,
                ReviewEntity.reviewed_id == reviewed_id,
                ReviewEntity.is_deleted == False
            )
            .first()
        )

    def get_by_product(
            self,
            product_id: int,
            limit: int = 20,
            offset: int = 0,
            sort_by: str = "recent"
    ) -> List[ReviewEntity]:
        """Récupérer les avis d'un produit"""
        query = self.db.query(ReviewEntity).filter(
            ReviewEntity.product_id == product_id,
            ReviewEntity.is_deleted == False,
            ReviewEntity.is_public == True
        )

        # Tri
        if sort_by == "recent":
            query = query.order_by(desc(ReviewEntity.created_at))
        elif sort_by == "helpful":
            query = query.order_by(desc(ReviewEntity.helpful_count))
        elif sort_by == "rating_high":
            query = query.order_by(desc(ReviewEntity.rating))
        elif sort_by == "rating_low":
            query = query.order_by(ReviewEntity.rating)

        return query.limit(limit).offset(offset).all()

    def count_by_product(self, product_id: int) -> int:
        """Compter les avis d'un produit"""
        return (
            self.db.query(ReviewEntity)
            .filter(
                ReviewEntity.product_id == product_id,
                ReviewEntity.is_deleted == False,
                ReviewEntity.is_public == True
            )
            .count()
        )

    def get_by_reviewer(self, reviewer_id: int) -> List[ReviewEntity]:
        """Récupérer les avis donnés par un utilisateur"""
        return (
            self.db.query(ReviewEntity)
            .filter(
                ReviewEntity.reviewer_id == reviewer_id,
                ReviewEntity.is_deleted == False
            )
            .order_by(desc(ReviewEntity.created_at))
            .all()
        )

    def get_by_reviewed_user(self, reviewed_id: int) -> List[ReviewEntity]:
        """Récupérer les avis reçus par un utilisateur"""
        return (
            self.db.query(ReviewEntity)
            .filter(
                ReviewEntity.reviewed_id == reviewed_id,
                ReviewEntity.is_deleted == False,
                ReviewEntity.is_public == True
            )
            .order_by(desc(ReviewEntity.created_at))
            .all()
        )

    def get_product_statistics(self, product_id: int) -> ReviewStatisticsSchema:
        """Calculer les statistiques d'avis d'un produit"""
        reviews = self.db.query(ReviewEntity).filter(
            ReviewEntity.product_id == product_id,
            ReviewEntity.is_deleted == False,
            ReviewEntity.is_public == True
        ).all()

        return self._calculate_statistics(reviews)

    def get_user_statistics(self, user_id: int) -> ReviewStatisticsSchema:
        """Calculer les statistiques d'avis d'un utilisateur"""
        reviews = self.db.query(ReviewEntity).filter(
            ReviewEntity.reviewed_id == user_id,
            ReviewEntity.is_deleted == False,
            ReviewEntity.is_public == True
        ).all()

        return self._calculate_statistics(reviews)

    def _calculate_statistics(self, reviews: List[ReviewEntity]) -> ReviewStatisticsSchema:
        """Calculer les statistiques à partir d'une liste d'avis"""
        if not reviews:
            return ReviewStatisticsSchema()

        total = len(reviews)
        total_rating = sum(r.rating for r in reviews)
        average_rating = round(total_rating / total, 2)

        # Distribution des notes
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            distribution[review.rating] += 1

        # Pourcentages
        percentages = {
            f"percentage_{i}_star{'s' if i > 1 else ''}": round((count / total) * 100, 1)
            for i, count in distribution.items()
        }

        # Avis vérifiés
        verified_count = len([r for r in reviews if r.is_verified])
        verified_percentage = round((verified_count / total) * 100, 1)

        # Moyennes des critères détaillés
        quality_ratings = [r.quality_rating for r in reviews if r.quality_rating]
        delivery_ratings = [r.delivery_rating for r in reviews if r.delivery_rating]
        service_ratings = [r.service_rating for r in reviews if r.service_rating]
        value_ratings = [r.value_rating for r in reviews if r.value_rating]

        return ReviewStatisticsSchema(
            total_reviews=total,
            average_rating=average_rating,
            rating_distribution=distribution,
            average_quality_rating=round(sum(quality_ratings) / len(quality_ratings), 2) if quality_ratings else None,
            average_delivery_rating=round(sum(delivery_ratings) / len(delivery_ratings),
                                          2) if delivery_ratings else None,
            average_service_rating=round(sum(service_ratings) / len(service_ratings), 2) if service_ratings else None,
            average_value_rating=round(sum(value_ratings) / len(value_ratings), 2) if value_ratings else None,
            verified_reviews_count=verified_count,
            verified_percentage=verified_percentage,
            **percentages
        )


class ReviewHelpfulVoteRepository(BaseRepository):
    """Repository pour les votes d'utilité"""

    def __init__(self, db: Session):
        super().__init__(db, ReviewHelpfulVoteEntity)

    def get_by_review_and_user(
            self,
            review_id: int,
            user_id: int
    ) -> Optional[ReviewHelpfulVoteEntity]:
        """Récupérer le vote d'un utilisateur pour un avis"""
        return (
            self.db.query(ReviewHelpfulVoteEntity)
            .filter(
                ReviewHelpfulVoteEntity.review_id == review_id,
                ReviewHelpfulVoteEntity.user_id == user_id
            )
            .first()
        )