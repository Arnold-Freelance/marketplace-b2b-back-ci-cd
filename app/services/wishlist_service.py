"""
Service pour gérer la wishlist/favoris
"""
from typing import List
from decimal import Decimal

from app.repositories.favorite_repo import FavoriteRepository
from app.repositories.product_repo import ProductRepository
from app.schemas.favorite import (
    FavoriteSchema, AddToFavoritesSchema, UpdateFavoriteSchema,
    FavoriteStatisticsSchema
)
from app.schemas.base import ResponseBase
from app.mappers.favorite_mapper import FavoriteMapper
from app.core.exceptions import ValidationError, NotFoundError, BusinessRuleError
from app.core.logger import logger


class WishlistService:
    """Service pour gérer la wishlist"""

    def __init__(
            self,
            favorite_repo: FavoriteRepository,
            product_repo: ProductRepository
    ):
        self.favorite_repo = favorite_repo
        self.product_repo = product_repo

    def add_to_favorites(
            self,
            user_id: int,
            data: AddToFavoritesSchema
    ) -> ResponseBase[FavoriteSchema]:
        """
        Ajouter un produit aux favoris
        """
        try:
            # Vérifier que le produit existe
            product = self.product_repo.get_by_id(data.product_id)
            if not product:
                raise NotFoundError("Produit non trouvé")

            # Vérifier que le produit n'est pas déjà dans les favoris
            existing = self.favorite_repo.get_by_user_and_product(
                user_id,
                data.product_id
            )

            if existing:
                raise BusinessRuleError("Ce produit est déjà dans vos favoris")

            # Ajouter aux favoris
            favorite = self.favorite_repo.create(
                user_id=user_id,
                product_id=data.product_id,
                notes=data.notes,
                priority=data.priority,
                notification_enabled=data.notification_enabled,
                price_at_add=product.price
            )

            logger.info(f"Produit {data.product_id} ajouté aux favoris de user {user_id}")

            # Convertir et enrichir
            favorite_schema = FavoriteMapper.entity_to_schema(favorite)
            favorite_schema = self._enrich_favorite(favorite_schema)

            return ResponseBase[FavoriteSchema](
                success=True,
                message="Produit ajouté aux favoris",
                item=favorite_schema
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur ajout favoris: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def remove_from_favorites(
            self,
            user_id: int,
            favorite_id: int
    ) -> ResponseBase[FavoriteSchema]:
        """
        Retirer un produit des favoris
        """
        try:
            favorite = self.favorite_repo.get_by_id(favorite_id)
            if not favorite:
                raise NotFoundError("Favori non trouvé")

            # Vérifier que le favori appartient à l'utilisateur
            if favorite.user_id != user_id:
                raise BusinessRuleError("Ce favori ne vous appartient pas")

            # Supprimer
            self.favorite_repo.delete(favorite_id)

            logger.info(f"Favori {favorite_id} supprimé")

            return ResponseBase[FavoriteSchema](
                success=True,
                message="Produit retiré des favoris"
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur suppression favori: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def update_favorite(
            self,
            user_id: int,
            data: UpdateFavoriteSchema
    ) -> ResponseBase[FavoriteSchema]:
        """
        Mettre à jour un favori
        """
        try:
            favorite = self.favorite_repo.get_by_id(data.favorite_id)
            if not favorite:
                raise NotFoundError("Favori non trouvé")

            # Vérifier que le favori appartient à l'utilisateur
            if favorite.user_id != user_id:
                raise BusinessRuleError("Ce favori ne vous appartient pas")

            # Mettre à jour
            update_data = data.model_dump(exclude_none=True, exclude={'favorite_id'})
            self.favorite_repo.update(data.favorite_id, **update_data)

            logger.info(f"Favori {data.favorite_id} mis à jour")

            # Récupérer le favori mis à jour
            favorite = self.favorite_repo.get_by_id(data.favorite_id)
            favorite_schema = FavoriteMapper.entity_to_schema(favorite)
            favorite_schema = self._enrich_favorite(favorite_schema)

            return ResponseBase[FavoriteSchema](
                success=True,
                message="Favori mis à jour",
                item=favorite_schema
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur mise à jour favori: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def get_my_favorites(self, user_id: int) -> ResponseBase[FavoriteSchema]:
        """
        Récupérer tous les favoris d'un utilisateur
        """
        try:
            favorites = self.favorite_repo.get_by_user(user_id)

            # Convertir et enrichir
            favorites_schema = [
                FavoriteMapper.entity_to_schema(fav)
                for fav in favorites
            ]
            favorites_schema = [
                self._enrich_favorite(fav)
                for fav in favorites_schema
            ]

            # Trier par priorité puis date
            favorites_schema.sort(
                key=lambda x: (-x.priority, x.created_at),
                reverse=False
            )

            return ResponseBase[FavoriteSchema](
                success=True,
                message="Favoris récupérés",
                items=favorites_schema,
                total=len(favorites_schema)
            )

        except Exception as e:
            logger.error(f"Erreur récupération favoris: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def get_favorites_statistics(
            self,
            user_id: int
    ) -> ResponseBase[FavoriteStatisticsSchema]:
        """
        Récupérer les statistiques des favoris
        """
        try:
            favorites = self.favorite_repo.get_by_user(user_id)

            stats = FavoriteStatisticsSchema(
                total_favorites=len(favorites),
                available_products=0,
                unavailable_products=0,
                products_with_price_drop=0,
                total_potential_savings=Decimal("0.00")
            )

            for favorite in favorites:
                product = self.product_repo.get_by_id(favorite.product_id)

                if product:
                    # Disponibilité
                    if product.is_active and product.stock_quantity > 0:
                        stats.available_products += 1
                    else:
                        stats.unavailable_products += 1

                    # Baisse de prix
                    if favorite.price_at_add and product.price < favorite.price_at_add:
                        stats.products_with_price_drop += 1
                        savings = favorite.price_at_add - product.price
                        stats.total_potential_savings += savings

            return ResponseBase[FavoriteStatisticsSchema](
                success=True,
                message="Statistiques récupérées",
                item=stats
            )

        except Exception as e:
            logger.error(f"Erreur statistiques favoris: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def check_is_favorite(
            self,
            user_id: int,
            product_id: int
    ) -> bool:
        """
        Vérifier si un produit est dans les favoris
        """
        try:
            favorite = self.favorite_repo.get_by_user_and_product(user_id, product_id)
            return favorite is not None
        except Exception as e:
            logger.error(f"Erreur vérification favori: {e}")
            return False

    def _enrich_favorite(self, favorite: FavoriteSchema) -> FavoriteSchema:
        """Enrichir un favori avec les informations du produit"""
        product = self.product_repo.get_by_id(favorite.product_id)

        if product:
            favorite.product_name = product.name
            favorite.product_slug = product.slug
            favorite.product_price = product.price
            favorite.product_is_available = product.is_active and product.stock_quantity > 0
            favorite.product_stock = product.stock_quantity

            # Image principale
            if product.product_images:
                primary_image = next(
                    (img for img in product.product_images if img.is_primary and not img.is_deleted),
                    None
                )
                if primary_image:
                    favorite.product_image = primary_image.thumbnail_url
                elif product.product_images:
                    favorite.product_image = product.product_images[0].thumbnail_url

            # Alerte baisse de prix
            if favorite.price_at_add and product.price < favorite.price_at_add:
                favorite.price_dropped = True
                favorite.price_difference = favorite.price_at_add - product.price

        return favorite