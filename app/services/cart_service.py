# app/services/cart_service.py
"""
Service pour gérer le panier d'achat
"""
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timedelta

from app.repositories.cart_repo import CartRepository, CartItemRepository
from app.repositories.product_repo import ProductRepository
from app.schemas.cart import CartSchema, CartItemSchema, AddToCartSchema, UpdateCartItemSchema
from app.schemas.base import ResponseBase
from app.mappers.cart_mapper import CartMapper
from app.core.exceptions import ValidationError, NotFoundError, BusinessRuleError
from app.core.logger import logger


class CartService:
    """Service pour gérer le panier"""

    def __init__(
            self,
            cart_repo: CartRepository,
            cart_item_repo: CartItemRepository,
            product_repo: ProductRepository
    ):
        self.cart_repo = cart_repo
        self.cart_item_repo = cart_item_repo
        self.product_repo = product_repo

    def get_or_create_cart(self, user_id: int) -> ResponseBase[CartSchema]:
        """
        Récupérer le panier actif de l'utilisateur ou en créer un nouveau
        """
        try:
            # Chercher un panier actif
            cart = self.cart_repo.get_active_cart(user_id)

            if not cart:
                # Créer un nouveau panier
                cart = self.cart_repo.create(
                    user_id=user_id,
                    is_active=True,
                    expires_at=datetime.now() + timedelta(days=30)
                )
                logger.info(f"Nouveau panier créé pour utilisateur {user_id}")

            # Enrichir avec les items
            cart_schema = CartMapper.entity_to_schema(cart)
            cart_schema = self._enrich_cart(cart_schema)

            return ResponseBase[CartSchema](
                success=True,
                message="Panier récupéré avec succès",
                item=cart_schema
            )

        except Exception as e:
            logger.error(f"Erreur récupération panier: {e}")
            raise Exception(f"Erreur lors de la récupération du panier: {str(e)}")

    def add_to_cart(self, user_id: int, data: AddToCartSchema) -> ResponseBase[CartSchema]:
        """
        Ajouter un produit au panier
        """
        try:
            # Vérifier que le produit existe et est disponible
            product = self.product_repo.get_by_id(data.product_id)
            if not product:
                raise NotFoundError(f"Produit {data.product_id} non trouvé")

            if not product.is_active:
                raise BusinessRuleError("Ce produit n'est plus disponible")

            # Vérifier le stock
            if product.stock_quantity < data.quantity:
                raise BusinessRuleError(
                    f"Stock insuffisant. Disponible: {product.stock_quantity}"
                )

            # Récupérer ou créer le panier
            cart = self.cart_repo.get_active_cart(user_id)
            if not cart:
                cart = self.cart_repo.create(
                    user_id=user_id,
                    is_active=True,
                    expires_at=datetime.now() + timedelta(days=30)
                )

            # Vérifier si le produit est déjà dans le panier
            existing_item = self.cart_item_repo.get_by_cart_and_product(
                cart.id, data.product_id
            )

            if existing_item:
                # Additionner la quantité demandée à l'existante (produit déjà au panier).
                new_quantity = existing_item.quantity + data.quantity

                # Vérifier le stock pour la nouvelle quantité
                if product.stock_quantity < new_quantity:
                    raise BusinessRuleError(
                        f"Stock insuffisant pour cette quantité. Disponible: {product.stock_quantity}"
                    )

                self.cart_item_repo.update(
                    existing_item.id,
                    quantity=new_quantity,
                    unit_price=product.price,
                    subtotal=product.price * new_quantity
                )
                logger.info(f"Quantité mise à jour dans le panier: {new_quantity}")
            else:
                # Ajouter un nouvel item
                self.cart_item_repo.create(
                    cart_id=cart.id,
                    product_id=data.product_id,
                    quantity=data.quantity,
                    unit_price=product.price,
                    subtotal=product.price * data.quantity
                )
                logger.info(f"Produit {data.product_id} ajouté au panier")

            # Récupérer le panier mis à jour
            cart = self.cart_repo.get_by_id(cart.id)
            cart_schema = CartMapper.entity_to_schema(cart)
            cart_schema = self._enrich_cart(cart_schema)

            return ResponseBase[CartSchema](
                success=True,
                message="Produit ajouté au panier avec succès",
                item=cart_schema
            )

        except (ValidationError, NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur ajout au panier: {e}")
            raise Exception(f"Erreur lors de l'ajout au panier: {str(e)}")

    def update_cart_item(self, user_id: int, data: UpdateCartItemSchema) -> ResponseBase[CartSchema]:
        """
        Mettre à jour la quantité d'un item du panier
        """
        try:
            # Récupérer l'item
            cart_item = self.cart_item_repo.get_by_id(data.cart_item_id)
            if not cart_item:
                raise NotFoundError("Item non trouvé dans le panier")

            # Vérifier que l'item appartient à l'utilisateur
            cart = self.cart_repo.get_by_id(cart_item.cart_id)
            if cart.user_id != user_id:
                raise BusinessRuleError("Vous n'êtes pas autorisé à modifier cet item")

            # Vérifier le stock
            product = self.product_repo.get_by_id(cart_item.product_id)
            if product.stock_quantity < data.quantity:
                raise BusinessRuleError(
                    f"Stock insuffisant. Disponible: {product.stock_quantity}"
                )

            # Mettre à jour
            self.cart_item_repo.update(
                data.cart_item_id,
                quantity=data.quantity,
                unit_price=product.price,
                subtotal=product.price * data.quantity
            )

            logger.info(f"Item {data.cart_item_id} mis à jour: quantité {data.quantity}")

            # Récupérer le panier mis à jour
            cart = self.cart_repo.get_by_id(cart_item.cart_id)
            cart_schema = CartMapper.entity_to_schema(cart)
            cart_schema = self._enrich_cart(cart_schema)

            return ResponseBase[CartSchema](
                success=True,
                message="Panier mis à jour avec succès",
                item=cart_schema
            )

        except (ValidationError, NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur mise à jour panier: {e}")
            raise Exception(f"Erreur lors de la mise à jour: {str(e)}")

    def remove_from_cart(self, user_id: int, cart_item_id: int) -> ResponseBase[CartSchema]:
        """
        Retirer un item du panier
        """
        try:
            # Récupérer l'item
            cart_item = self.cart_item_repo.get_by_id(cart_item_id)
            if not cart_item:
                raise NotFoundError("Item non trouvé dans le panier")

            # Vérifier que l'item appartient à l'utilisateur
            cart = self.cart_repo.get_by_id(cart_item.cart_id)
            if cart.user_id != user_id:
                raise BusinessRuleError("Vous n'êtes pas autorisé à supprimer cet item")

            # Supprimer l'item
            self.cart_item_repo.delete(cart_item_id)

            logger.info(f"Item {cart_item_id} retiré du panier")

            # Récupérer le panier mis à jour
            cart = self.cart_repo.get_by_id(cart.id)
            cart_schema = CartMapper.entity_to_schema(cart)
            cart_schema = self._enrich_cart(cart_schema)

            return ResponseBase[CartSchema](
                success=True,
                message="Produit retiré du panier avec succès",
                item=cart_schema
            )

        except (ValidationError, NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur suppression item panier: {e}")
            raise Exception(f"Erreur lors de la suppression: {str(e)}")

    def clear_cart(self, user_id: int) -> ResponseBase[CartSchema]:
        """
        Vider complètement le panier
        """
        try:
            cart = self.cart_repo.get_active_cart(user_id)
            if not cart:
                raise NotFoundError("Panier non trouvé")

            # Supprimer tous les items
            self.cart_item_repo.delete_by_cart_id(cart.id)

            logger.info(f"Panier {cart.id} vidé")

            # Récupérer le panier vide
            cart = self.cart_repo.get_by_id(cart.id)
            cart_schema = CartMapper.entity_to_schema(cart)

            return ResponseBase[CartSchema](
                success=True,
                message="Panier vidé avec succès",
                item=cart_schema
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur vidage panier: {e}")
            raise Exception(f"Erreur lors du vidage du panier: {str(e)}")

    def merge_guest_cart(self, user_id: int, items: list) -> ResponseBase[CartSchema]:
        """Fusionner un panier invité (client) dans le panier serveur.

        - Additionne les quantités par produit (dédoublonnage).
        - Tolérant : produit inexistant/inactif/supprimé → ignoré ; quantité
          au-delà du stock → plafonnée. Ne lève jamais pour un item : la
          connexion ne doit pas échouer à cause d'un article devenu indisponible.
        """
        try:
            cart = self.cart_repo.get_active_cart(user_id)
            if not cart:
                cart = self.cart_repo.create(
                    user_id=user_id,
                    is_active=True,
                    expires_at=datetime.now() + timedelta(days=30),
                )

            skipped = 0
            for entry in items:
                product = self.product_repo.get_by_id(entry.product_id, raise_if_missing=False)
                if not product or not product.is_active or getattr(product, "is_deleted", False):
                    skipped += 1
                    continue
                if product.stock_quantity <= 0:
                    skipped += 1
                    continue

                existing = self.cart_item_repo.get_by_cart_and_product(cart.id, entry.product_id)
                current_qty = existing.quantity if existing else 0
                # Addition puis plafonnement au stock disponible.
                target_qty = min(current_qty + entry.quantity, product.stock_quantity)
                if target_qty <= 0:
                    continue

                if existing:
                    self.cart_item_repo.update(
                        existing.id,
                        quantity=target_qty,
                        unit_price=product.price,
                        subtotal=product.price * target_qty,
                    )
                else:
                    self.cart_item_repo.create(
                        cart_id=cart.id,
                        product_id=entry.product_id,
                        quantity=target_qty,
                        unit_price=product.price,
                        subtotal=product.price * target_qty,
                    )

            cart = self.cart_repo.get_by_id(cart.id)
            cart_schema = CartMapper.entity_to_schema(cart)
            cart_schema = self._enrich_cart(cart_schema)

            msg = "Panier fusionné avec succès"
            if skipped:
                msg += f" ({skipped} article(s) indisponible(s) ignoré(s))"

            return ResponseBase[CartSchema](success=True, message=msg, item=cart_schema)

        except Exception as e:
            logger.error(f"Erreur fusion panier: {e}")
            raise Exception(f"Erreur lors de la fusion du panier: {str(e)}")

    def _enrich_cart(self, cart_schema: CartSchema) -> CartSchema:
        """
        Enrichir le panier avec les informations des produits et calculer les totaux
        """
        subtotal = Decimal("0.00")
        items_count = 0

        for item in cart_schema.cart_items:
            # Récupérer le produit
            product = self.product_repo.get_by_id(item.product_id)
            if product:
                item.product_name = product.name
                item.product_slug = product.slug
                item.product_stock = product.stock_quantity
                item.is_available = product.is_active and product.stock_quantity > 0

                # Image principale
                if product.product_images:
                    primary_image = next(
                        (img for img in product.product_images if img.is_primary and not img.is_deleted),
                        None
                    )
                    if primary_image:
                        item.product_image_url = primary_image.thumbnail_url
                    elif product.product_images:
                        item.product_image_url = product.product_images[0].thumbnail_url

                # Mettre à jour le prix si changé
                if item.unit_price != product.price:
                    item.unit_price = product.price
                    item.subtotal = product.price * item.quantity

                subtotal += item.subtotal
                items_count += item.quantity

        cart_schema.subtotal = subtotal
        cart_schema.items_count = items_count

        return cart_schema