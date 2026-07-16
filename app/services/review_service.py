# app/services/review_service.py
"""
Service pour gérer les avis et évaluations
"""
from typing import List, Optional
from datetime import datetime

from app.repositories.review_repo import ReviewRepository, ReviewHelpfulVoteRepository
from app.repositories.order_repo import OrderRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.user_repo import UserRepository
from app.schemas.review import (
    ReviewSchema, CreateReviewSchema, UpdateReviewSchema,
    SupplierResponseSchema, ReviewHelpfulVoteSchema, ReviewStatisticsSchema
)
from app.schemas.base import ResponseBase
from app.mappers.review_mapper import ReviewMapper
from app.core.exceptions import ValidationError, NotFoundError, BusinessRuleError
from app.core.logger import logger
from app.models.order_entity import OrderStatus
from app.services.notification_service import NotificationService


class ReviewService:
    """Service pour gérer les avis"""

    def __init__(
            self,
            review_repo: ReviewRepository,
            review_vote_repo: ReviewHelpfulVoteRepository,
            order_repo: OrderRepository,
            product_repo: ProductRepository,
            user_repo: UserRepository,
            notification_service: Optional[NotificationService] = None,
    ):
        self.review_repo = review_repo
        self.review_vote_repo = review_vote_repo
        self.order_repo = order_repo
        self.product_repo = product_repo
        self.user_repo = user_repo
        self.notification_service = notification_service

    async def create_review(
            self,
            user_id: int,
            data: CreateReviewSchema
    ) -> ResponseBase[ReviewSchema]:
        """
        Créer un avis pour une commande
        """
        try:
            # Vérifier que la commande existe
            order = self.order_repo.get_by_id(data.order_id)
            if not order:
                raise NotFoundError("Commande non trouvée")

            # Vérifier que l'utilisateur est l'acheteur de la commande
            if order.buyer_id != user_id:
                raise BusinessRuleError("Vous ne pouvez évaluer que vos propres commandes")

            # Vérifier que la commande est livrée
            if order.status != OrderStatus.DELIVERED:
                raise BusinessRuleError("Vous ne pouvez évaluer qu'une commande livrée")

            # Vérifier qu'un avis n'existe pas déjà
            existing_review = self.review_repo.get_by_order_and_reviewer(
                data.order_id,
                user_id,
                order.supplier_id
            )

            if existing_review:
                raise BusinessRuleError("Vous avez déjà évalué cette commande")

            # Vérifier le produit si spécifié
            if data.product_id:
                product = self.product_repo.get_by_id(data.product_id)
                if not product:
                    raise NotFoundError("Produit non trouvé")

                # Vérifier que le produit fait partie de la commande
                product_in_order = any(
                    item.product_id == data.product_id
                    for item in order.order_items
                )

                if not product_in_order:
                    raise BusinessRuleError("Ce produit ne fait pas partie de la commande")

            # Créer l'avis
            review = self.review_repo.create(
                order_id=data.order_id,
                reviewer_id=user_id,
                reviewed_id=order.supplier_id,
                product_id=data.product_id,
                rating=data.rating,
                title=data.title,
                comment=data.comment,
                quality_rating=data.quality_rating,
                delivery_rating=data.delivery_rating,
                service_rating=data.service_rating,
                value_rating=data.value_rating,
                is_verified=True,  # Achat vérifié
                is_public=data.is_public
            )

            # Marquer la commande comme évaluée
            self.order_repo.update(order.id, is_reviewed=True)

            logger.info(f"Avis créé pour commande {order.id} par user {user_id}")

            # Notifier le fournisseur. Best-effort : l'avis reste publié même si
            # la notification échoue.
            if self.notification_service and review.product_id:
                try:
                    product = self.product_repo.get_by_id(review.product_id)
                    await self.notification_service.notify_review_received(
                        product_id=review.product_id,
                        supplier_id=review.reviewed_id,
                        product_name=product.name if product else "votre produit",
                        rating=review.rating,
                        actor_id=user_id,
                        review_id=review.id,
                    )
                except Exception as e:
                    logger.error(f"Notification 'avis reçu' non émise (avis publié): {e}")

            # Convertir en schema
            review_schema = ReviewMapper.entity_to_schema(review)
            review_schema = self._enrich_review(review_schema)

            return ResponseBase[ReviewSchema](
                success=True,
                message="Avis publié avec succès",
                item=review_schema
            )

        except (ValidationError, NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur création avis: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def update_review(
            self,
            user_id: int,
            data: UpdateReviewSchema
    ) -> ResponseBase[ReviewSchema]:
        """
        Mettre à jour un avis
        """
        try:
            review = self.review_repo.get_by_id(data.review_id)
            if not review:
                raise NotFoundError("Avis non trouvé")

            # Vérifier que l'utilisateur est l'auteur
            if review.reviewer_id != user_id:
                raise BusinessRuleError("Vous ne pouvez modifier que vos propres avis")

            # Préparer les données de mise à jour
            update_data = data.model_dump(exclude_none=True, exclude={'review_id'})

            # Mettre à jour
            self.review_repo.update(data.review_id, **update_data)

            logger.info(f"Avis {data.review_id} mis à jour")

            # Récupérer l'avis mis à jour
            review = self.review_repo.get_by_id(data.review_id)
            review_schema = ReviewMapper.entity_to_schema(review)
            review_schema = self._enrich_review(review_schema)

            return ResponseBase[ReviewSchema](
                success=True,
                message="Avis mis à jour avec succès",
                item=review_schema
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur mise à jour avis: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def add_supplier_response(
            self,
            user_id: int,
            data: SupplierResponseSchema
    ) -> ResponseBase[ReviewSchema]:
        """
        Ajouter une réponse du fournisseur à un avis
        """
        try:
            review = self.review_repo.get_by_id(data.review_id)
            if not review:
                raise NotFoundError("Avis non trouvé")

            # Vérifier que l'utilisateur est le fournisseur évalué
            if review.reviewed_id != user_id:
                raise BusinessRuleError("Vous ne pouvez répondre qu'aux avis vous concernant")

            # Vérifier qu'il n'y a pas déjà une réponse
            if review.supplier_response:
                raise BusinessRuleError("Vous avez déjà répondu à cet avis")

            # Ajouter la réponse
            self.review_repo.update(
                data.review_id,
                supplier_response=data.response,
                supplier_response_at=datetime.now()
            )

            logger.info(f"Réponse ajoutée à l'avis {data.review_id}")

            # Récupérer l'avis mis à jour
            review = self.review_repo.get_by_id(data.review_id)
            review_schema = ReviewMapper.entity_to_schema(review)
            review_schema = self._enrich_review(review_schema)

            return ResponseBase[ReviewSchema](
                success=True,
                message="Réponse publiée avec succès",
                item=review_schema
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur ajout réponse: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def vote_helpful(
            self,
            user_id: int,
            data: ReviewHelpfulVoteSchema
    ) -> ResponseBase[ReviewSchema]:
        """
        Voter sur l'utilité d'un avis
        """
        try:
            review = self.review_repo.get_by_id(data.review_id)
            if not review:
                raise NotFoundError("Avis non trouvé")

            # Vérifier qu'un vote n'existe pas déjà
            existing_vote = self.review_vote_repo.get_by_review_and_user(
                data.review_id,
                user_id
            )

            if existing_vote:
                # Mettre à jour le vote existant
                old_is_helpful = existing_vote.is_helpful
                self.review_vote_repo.update(existing_vote.id, is_helpful=data.is_helpful)

                # Mettre à jour les compteurs
                if old_is_helpful and not data.is_helpful:
                    self.review_repo.update(
                        data.review_id,
                        helpful_count=review.helpful_count - 1,
                        not_helpful_count=review.not_helpful_count + 1
                    )
                elif not old_is_helpful and data.is_helpful:
                    self.review_repo.update(
                        data.review_id,
                        helpful_count=review.helpful_count + 1,
                        not_helpful_count=review.not_helpful_count - 1
                    )
            else:
                # Créer un nouveau vote
                self.review_vote_repo.create(
                    review_id=data.review_id,
                    user_id=user_id,
                    is_helpful=data.is_helpful
                )

                # Mettre à jour les compteurs
                if data.is_helpful:
                    self.review_repo.update(
                        data.review_id,
                        helpful_count=review.helpful_count + 1
                    )
                else:
                    self.review_repo.update(
                        data.review_id,
                        not_helpful_count=review.not_helpful_count + 1
                    )

            logger.info(f"Vote enregistré pour avis {data.review_id}")

            # Récupérer l'avis mis à jour
            review = self.review_repo.get_by_id(data.review_id)
            review_schema = ReviewMapper.entity_to_schema(review)

            return ResponseBase[ReviewSchema](
                success=True,
                message="Vote enregistré",
                item=review_schema
            )

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Erreur vote avis: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def get_product_reviews(
            self,
            product_id: int,
            limit: int = 20,
            offset: int = 0,
            sort_by: str = "recent"  # recent, helpful, rating_high, rating_low
    ) -> ResponseBase[ReviewSchema]:
        """
        Récupérer les avis d'un produit
        """
        try:
            product = self.product_repo.get_by_id(product_id)
            if not product:
                raise NotFoundError("Produit non trouvé")

            # Récupérer les avis
            reviews = self.review_repo.get_by_product(
                product_id,
                limit,
                offset,
                sort_by
            )

            # Convertir et enrichir
            reviews_schema = [
                ReviewMapper.entity_to_schema(review)
                for review in reviews
            ]
            reviews_schema = [
                self._enrich_review(review)
                for review in reviews_schema
            ]

            # Compter le total
            total = self.review_repo.count_by_product(product_id)

            return ResponseBase[ReviewSchema](
                success=True,
                message="Avis récupérés",
                items=reviews_schema,
                total=total,
                limit=limit,
                offset=offset
            )

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Erreur récupération avis produit: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def get_user_reviews(
            self,
            user_id: int,
            as_reviewer: bool = True
    ) -> ResponseBase[ReviewSchema]:
        """
        Récupérer les avis d'un utilisateur
        """
        try:
            if as_reviewer:
                reviews = self.review_repo.get_by_reviewer(user_id)
            else:
                reviews = self.review_repo.get_by_reviewed_user(user_id)

            reviews_schema = [
                ReviewMapper.entity_to_schema(review)
                for review in reviews
            ]
            reviews_schema = [
                self._enrich_review(review)
                for review in reviews_schema
            ]

            return ResponseBase[ReviewSchema](
                success=True,
                message="Avis récupérés",
                items=reviews_schema,
                total=len(reviews_schema)
            )

        except Exception as e:
            logger.error(f"Erreur récupération avis utilisateur: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def get_review_statistics(
            self,
            product_id: Optional[int] = None,
            user_id: Optional[int] = None
    ) -> ResponseBase[ReviewStatisticsSchema]:
        """
        Récupérer les statistiques d'avis
        """
        try:
            if product_id:
                stats = self.review_repo.get_product_statistics(product_id)
            elif user_id:
                stats = self.review_repo.get_user_statistics(user_id)
            else:
                raise ValidationError("product_id ou user_id requis")

            return ResponseBase[ReviewStatisticsSchema](
                success=True,
                message="Statistiques récupérées",
                item=stats
            )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Erreur statistiques: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def _enrich_review(self, review: ReviewSchema) -> ReviewSchema:
        """Enrichir un avis avec les informations supplémentaires"""
        # Informations du reviewer
        reviewer = self.user_repo.get_by_id(review.reviewer_id)
        if reviewer:
            review.reviewer_name = f"{reviewer.first_name} {reviewer.last_name}"
            review.reviewer_avatar = getattr(reviewer, 'avatar_url', None)

        # Informations du produit
        if review.product_id:
            product = self.product_repo.get_by_id(review.product_id)
            if product:
                review.product_name = product.name
                if product.product_images:
                    primary_image = next(
                        (img for img in product.product_images if img.is_primary),
                        None
                    )
                    review.product_image = primary_image.thumbnail_url if primary_image else None

        # Calcul de la moyenne des notes détaillées
        detailed_ratings = [
            review.quality_rating,
            review.delivery_rating,
            review.service_rating,
            review.value_rating
        ]
        valid_ratings = [r for r in detailed_ratings if r is not None]

        if valid_ratings:
            review.average_detailed_rating = round(sum(valid_ratings) / len(valid_ratings), 2)

        return review