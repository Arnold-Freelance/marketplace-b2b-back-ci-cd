# app/services/product_service.py
from typing import List, Optional
from sqlalchemy.exc import IntegrityError

from app.repositories.product_repo import ProductRepository
from app.repositories.category_repo import CategoryRepo
from app.repositories.user_repo import UserRepository
from app.schemas.product import ProductSchema
from app.schemas.base import RequestBase, ResponseBase
from app.mappers.product_mapper import ProductMapper
from app.core.exceptions import ValidationError, NotFoundError, BusinessRuleError
from app.core.logger import logger


class ProductService:
    """Service pour gérer les opérations CRUD sur les produits"""

    def __init__(
            self,
            product_repo: ProductRepository,
            category_repo: CategoryRepo,
            user_repo: UserRepository
    ):
        self.product_repo = product_repo
        self.category_repo = category_repo
        self.user_repo = user_repo

    # ==================== AUTORISATION (T6) ====================

    def _roles_of(self, user_id: int) -> set:
        """Rôles du caller — source de vérité DB (avec fallback `role_names`)."""
        user = self.user_repo.get_by_id(user_id, raise_if_missing=False)
        return set(user.role_names) if user else set()

    @staticmethod
    def _can_write_product(product_supplier_id: int, caller_id: int, caller_roles: set) -> bool:
        """Écriture autorisée si **propriétaire OU admin** (T6).

        L'admin peut agir sur le produit de n'importe quel fournisseur (édition,
        suppression, stock). L'`updated_by` posé par l'appelant garde la trace de
        qui a réellement agi.
        """
        return caller_id == product_supplier_id or "admin" in caller_roles

    def create(self, request: RequestBase[ProductSchema]) -> ResponseBase[ProductSchema]:
        """Créer un nouveau produit avec validation complète"""

        # Validation des données d'entrée
        validation_errors = self._validate_create_request(request)
        if validation_errors:
            raise ValidationError(", ".join(validation_errors))

        try:
            data = request.data

            # Vérifier que le caller existe et récupérer ses rôles (T6)
            caller = self.user_repo.get_by_id(request.user, raise_if_missing=False)
            if not caller:
                raise NotFoundError(f"L'utilisateur avec l'ID {request.user} n'existe pas")
            caller_roles = set(caller.role_names)
            is_admin = "admin" in caller_roles
            is_supplier = "supplier" in caller_roles

            # Résolution du propriétaire du produit (T6) :
            # - admin  → crée AU NOM d'un fournisseur : supplier_id cible obligatoire + validé.
            # - supplier → crée pour lui-même.
            # - autre (buyer seul) → interdit.
            if is_admin and data.supplier_id:
                target = self.user_repo.get_by_id(data.supplier_id, raise_if_missing=False)
                if not target:
                    raise NotFoundError(
                        f"Le fournisseur cible {data.supplier_id} n'existe pas"
                    )
                if "supplier" not in set(target.role_names):
                    raise BusinessRuleError(
                        f"L'utilisateur {data.supplier_id} n'est pas un fournisseur"
                    )
                owner_id = data.supplier_id
            elif is_admin:
                raise ValidationError(
                    "En tant qu'administrateur, précisez le supplier_id du fournisseur "
                    "au nom duquel créer le produit"
                )
            elif is_supplier:
                owner_id = request.user
            else:
                raise BusinessRuleError(
                    "Seul un fournisseur ou un administrateur peut créer un produit"
                )

            # Vérifier que la catégorie existe
            category = self.category_repo.get_by_id(data.category_id)
            if not category:
                raise NotFoundError(f"La catégorie avec l'ID {data.category_id} n'existe pas")

            # Vérifier l'unicité du SKU si fourni
            if data.sku:
                existing_sku = self.product_repo.get_by_sku(data.sku)
                if existing_sku:
                    raise BusinessRuleError(f"Un produit avec le SKU '{data.sku}' existe déjà")

            # Vérifier l'unicité du slug
            existing_slug = self.product_repo.get_by_slug(data.slug)
            if existing_slug:
                raise BusinessRuleError(f"Un produit avec le slug '{data.slug}' existe déjà")

            # Préparer les données pour la création. On exclut supplier_id du dump
            # (résolu ci-dessus via owner_id) pour empêcher tout client de forcer
            # un propriétaire arbitraire.
            product_data = data.model_dump(exclude_none=True, exclude={'supplier_id'})
            product_data['supplier_id'] = owner_id
            product_data['updated_by'] = request.user  # traçabilité : créateur réel
            product_data['is_deleted'] = False
            product_data['views_count'] = 0

            # Gestion des attributs - s'assurer que c'est un dict
            if 'attributes' in product_data and product_data['attributes'] is None:
                product_data['attributes'] = {}

            # Créer le produit
            new_product = self.product_repo.create(**product_data)

            logger.info(f"Produit créé avec succès - ID: {new_product.id}, SKU: {new_product.sku}")

            # Convertir en schema pour la réponse
            product_schema = ProductMapper.entity_to_schema(new_product)

            return ResponseBase[ProductSchema](
                success=True,
                message="Produit créé avec succès",
                item=product_schema
            )

        except (ValidationError, NotFoundError, BusinessRuleError):
            raise
        except IntegrityError as e:
            logger.error(f"Erreur d'intégrité lors de la création du produit: {e}")
            raise BusinessRuleError("Erreur d'intégrité de données (contrainte violée)")
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la création du produit: {e}")
            raise Exception(f"Erreur interne lors de la création du produit: {str(e)}")

    def update(self, request: RequestBase[ProductSchema]) -> ResponseBase[ProductSchema]:
        """Mettre à jour un produit existant"""

        # Validation des données d'entrée
        validation_errors = self._validate_update_request(request)
        if validation_errors:
            raise ValidationError(", ".join(validation_errors))

        #try:
        data = request.data

        # Vérifier que le produit existe
        existing_product = self.product_repo.get_by_id(data.id)
        if not existing_product:
            raise NotFoundError(f"Le produit avec l'ID {data.id} n'existe pas")

        # Autorisation (T6) : propriétaire OU admin.
        if not self._can_write_product(
            existing_product.supplier_id, request.user, self._roles_of(request.user)
        ):
            raise BusinessRuleError("Vous n'êtes pas autorisé à modifier ce produit")

        # Vérifier la catégorie si changée
        if data.category_id and data.category_id != existing_product.category_id:
            category = self.category_repo.get_by_id(data.category_id)
            if not category:
                raise NotFoundError(f"La catégorie avec l'ID {data.category_id} n'existe pas")

        # Vérifier l'unicité du SKU si changé
        if data.sku and data.sku != existing_product.sku:
            existing_sku = self.product_repo.get_by_sku(data.sku)
            if existing_sku and existing_sku.id != data.id:
                raise BusinessRuleError(f"Un produit avec le SKU '{data.sku}' existe déjà")

        # Vérifier l'unicité du slug si changé
        if data.slug and data.slug != existing_product.slug:
            existing_slug = self.product_repo.get_by_slug(data.slug)
            if existing_slug and existing_slug.id != data.id:
                raise BusinessRuleError(f"Un produit avec le slug '{data.slug}' existe déjà")

        # Préparer les données de mise à jour.
        #
        # Le `@model_serializer` custom de `MyBase` reconstruit le dict à la main et
        # droppe déjà les None, MAIS ignore le paramètre `exclude` de model_dump().
        # On retire donc à la main les seules clés qui, non-nulles, feraient du tort
        # via le setattr du repo :
        #   - product_images : relation cascade="all, delete-orphan" ; son défaut []
        #     EFFACERAIT toutes les images à chaque save (bug corrigé ici).
        #   - views_count    : défaut 0 → remettrait le compteur de vues à zéro.
        #   - id/supplier_id : immuables (supplier_id = garde-fou anti-réassignation
        #     de propriétaire si un client l'envoie).
        #   - average_rating/reviews_count : @property sans setter → setattr lèverait
        #     AttributeError (500) pour un client qui relit puis renvoie l'objet entier.
        _READ_ONLY_FIELDS = {
            'id', 'supplier_id',
            'product_images', 'views_count',
            'average_rating', 'reviews_count',
        }
        update_data = {
            k: v for k, v in data.model_dump().items() if k not in _READ_ONLY_FIELDS
        }
        update_data['updated_by'] = request.user

        # Mise à jour du produit
        updated_product = self.product_repo.update(data.id, **update_data)

        logger.info(f"Produit mis à jour - ID: {data.id}")

        # Convertir en schema pour la réponse
        product_schema = ProductMapper.entity_to_schema(updated_product)

        return ResponseBase[ProductSchema](
            success=True,
            message="Produit modifié avec succès",
            item=product_schema
        )

        # except (ValidationError, NotFoundError, BusinessRuleError):
        #     raise
        # except Exception as e:
        #     logger.error(f"Erreur lors de la mise à jour du produit: {e}")
        #     raise Exception(f"Erreur interne lors de la mise à jour: {str(e)}")

    def delete(self, request: RequestBase[ProductSchema]) -> ResponseBase[ProductSchema]:
        """Supprimer un produit (soft delete)"""

        # Validation
        validation_errors = self._validate_delete_request(request)
        if validation_errors:
            raise ValidationError(", ".join(validation_errors))

        try:
            data = request.data

            # Vérifier que le produit existe
            existing_product = self.product_repo.get_by_id(data.id)
            if not existing_product:
                raise NotFoundError(f"Le produit avec l'ID {data.id} n'existe pas")

            # Autorisation (T6) : propriétaire OU admin.
            if not self._can_write_product(
                existing_product.supplier_id, request.user, self._roles_of(request.user)
            ):
                raise BusinessRuleError("Vous n'êtes pas autorisé à supprimer ce produit")

            # Soft delete
            self.product_repo.update(
                data.id,
                is_deleted=True,
                is_active=False,
                updated_by=request.user
            )

            logger.info(f"Produit supprimé - ID: {data.id}")

            return ResponseBase[ProductSchema](
                success=True,
                message="Produit supprimé avec succès"
            )

        except (ValidationError, NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du produit: {e}")
            raise Exception(f"Erreur interne lors de la suppression: {str(e)}")

    def get_by_id(self, product_id: int) -> ResponseBase[ProductSchema]:
        """Récupérer un produit par son ID"""
        try:
            product = self.product_repo.get_by_id(product_id)
            if not product:
                raise NotFoundError(f"Le produit avec l'ID {product_id} n'existe pas")

            # Incrémenter le compteur de vues
            self.product_repo.increment_views(product_id)

            # Convertir en schema
            product_schema = ProductMapper.entity_to_schema(product)

            return ResponseBase[ProductSchema](
                success=True,
                message="Produit récupéré avec succès",
                item=product_schema
            )

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du produit: {e}")
            raise Exception(f"Erreur interne: {str(e)}")

    def get_by_slug(self, slug: str) -> ResponseBase[ProductSchema]:
        """Récupérer un produit par son slug"""
        try:
            product = self.product_repo.get_by_slug(slug)
            if not product:
                raise NotFoundError(f"Le produit avec le slug '{slug}' n'existe pas")

            # Incrémenter le compteur de vues
            self.product_repo.increment_views(product.id)

            # Convertir en schema
            product_schema = ProductMapper.entity_to_schema(product)

            return ResponseBase[ProductSchema](
                success=True,
                message="Produit récupéré avec succès",
                item=product_schema
            )

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du produit: {e}")
            raise Exception(f"Erreur interne: {str(e)}")

    def get_by_criteria(self, request: RequestBase[ProductSchema]) -> ResponseBase[ProductSchema]:
        """Récupérer les produits selon critères avec pagination"""
        try:
            # Comptage
            count = self.product_repo.count(request)

            if count == 0:
                return ResponseBase[ProductSchema](
                    success=True,
                    message="Aucun produit trouvé",
                    items=[],
                    total=0,
                    limit=request.limit,
                    offset=request.offset
                )

            # Récupération des produits
            products = self.product_repo.get_by_criteria(request)

            # Convertir en schemas
            products_schema = ProductMapper.entities_to_schemas(products)

            return ResponseBase[ProductSchema](
                success=True,
                message="Produits récupérés avec succès",
                items=products_schema,
                total=count,
                limit=request.limit,
                offset=request.offset
            )

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des produits: {e}")
            raise Exception(f"Erreur interne: {str(e)}")

    def get_showcase(self, limit: int = 10) -> ResponseBase[ProductSchema]:
        """Vitrine de l'accueil : curation d'abord, complétée par les plus vus.

        Volontairement non paginée — c'est un carrousel de tête, pas le
        catalogue : celui-ci se parcourt via `get_by_criteria` (limit/offset).
        `total` reflète donc ce qui est renvoyé.
        """
        try:
            products = self.product_repo.get_showcase(limit)
            products_schema = ProductMapper.entities_to_schemas(products)

            return ResponseBase[ProductSchema](
                success=True,
                message="Produits récupérés avec succès",
                items=products_schema,
                total=len(products_schema),
                limit=limit,
                offset=0
            )

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la vitrine: {e}")
            raise Exception(f"Erreur interne: {str(e)}")

    def update_stock(self, product_id: int, quantity: int, user_id: int) -> ResponseBase[ProductSchema]:
        """Mettre à jour le stock d'un produit"""
        try:
            if quantity < 0:
                raise ValidationError("La quantité ne peut pas être négative")

            product = self.product_repo.get_by_id(product_id)
            if not product:
                raise NotFoundError(f"Le produit avec l'ID {product_id} n'existe pas")

            # Autorisation (T6) : propriétaire OU admin.
            if not self._can_write_product(
                product.supplier_id, user_id, self._roles_of(user_id)
            ):
                raise BusinessRuleError("Vous n'êtes pas autorisé à modifier ce stock")

            # Met à jour le stock + trace l'auteur réel (admin ou fournisseur).
            updated_product = self.product_repo.update(
                product_id, stock_quantity=quantity, updated_by=user_id
            )
            product_schema = ProductMapper.entity_to_schema(updated_product)

            logger.info(f"Stock mis à jour pour le produit {product_id}: {quantity}")

            return ResponseBase[ProductSchema](
                success=True,
                message="Stock mis à jour avec succès",
                item=product_schema
            )

        except (ValidationError, NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du stock: {e}")
            raise Exception(f"Erreur interne: {str(e)}")

    # ==================== MÉTHODES DE VALIDATION ====================

    def _validate_create_request(self, request: RequestBase[ProductSchema]) -> List[str]:
        """Valider la requête de création"""
        errors = []

        # Validation user_id
        if not request.user:
            errors.append("L'ID utilisateur est obligatoire")

        # Validation des données
        if not request.data:
            errors.append("Les données du produit sont obligatoires")
            return errors

        data = request.data

        # Validation du nom
        if not data.name or not data.name.strip():
            errors.append("Le nom du produit est obligatoire")
        elif len(data.name.strip()) < 2:
            errors.append("Le nom du produit doit contenir au moins 2 caractères")
        elif len(data.name.strip()) > 255:
            errors.append("Le nom du produit ne peut pas dépasser 255 caractères")

        # Validation du slug
        if not data.slug or not data.slug.strip():
            errors.append("Le slug du produit est obligatoire")
        elif len(data.slug.strip()) < 2:
            errors.append("Le slug doit contenir au moins 2 caractères")

        # Validation de la catégorie
        if not data.category_id:
            errors.append("La catégorie est obligatoire")
        elif data.category_id <= 0:
            errors.append("L'ID de la catégorie doit être positif")

        # Validation du prix
        if data.price is None:
            errors.append("Le prix est obligatoire")
        elif data.price <= 0:
            errors.append("Le prix doit être supérieur à 0")

        # Validation de la short_description
        if data.short_description and len(data.short_description) > 500:
            errors.append("La description courte ne peut pas dépasser 500 caractères")

        # Validation du SKU
        if data.sku and len(data.sku) > 100:
            errors.append("Le SKU ne peut pas dépasser 100 caractères")

        # Validation des quantités
        if data.min_order_quantity is not None and data.min_order_quantity < 1:
            errors.append("La quantité minimum de commande doit être au moins 1")

        if data.stock_quantity is not None and data.stock_quantity < 0:
            errors.append("La quantité en stock ne peut pas être négative")

        # Validation de la devise
        if data.currency and len(data.currency) != 3:
            errors.append("La devise doit être un code ISO à 3 lettres (ex: XOF, USD, EUR)")



        # Validation des attributs
        if data.attributes and not isinstance(data.attributes, dict):
            errors.append("Les attributs doivent être un objet JSON")

        return errors

    def _validate_update_request(self, request: RequestBase[ProductSchema]) -> List[str]:
        """Valider la requête de mise à jour"""
        errors = []

        # Validation user_id
        if not request.user:
            errors.append("L'ID utilisateur est obligatoire")

        # Validation des données
        if not request.data:
            errors.append("Les données du produit sont obligatoires")
            return errors

        data = request.data

        # Validation de l'ID
        if not data.id:
            errors.append("L'ID du produit est obligatoire")
        elif data.id <= 0:
            errors.append("L'ID du produit doit être positif")

        # Validation du nom si fourni
        if data.name is not None:
            if not data.name.strip():
                errors.append("Le nom du produit ne peut pas être vide")
            elif len(data.name.strip()) < 2:
                errors.append("Le nom du produit doit contenir au moins 2 caractères")
            elif len(data.name.strip()) > 255:
                errors.append("Le nom du produit ne peut pas dépasser 255 caractères")

        # Validation du slug si fourni
        if data.slug is not None:
            if not data.slug.strip():
                errors.append("Le slug ne peut pas être vide")
            elif len(data.slug.strip()) < 2:
                errors.append("Le slug doit contenir au moins 2 caractères")

        # Validation de la catégorie si fournie
        if data.category_id is not None and data.category_id <= 0:
            errors.append("L'ID de la catégorie doit être positif")

        # Validation du prix si fourni
        if data.price is not None and data.price <= 0:
            errors.append("Le prix doit être supérieur à 0")

        # Validation de la short_description si fournie
        if data.short_description is not None and len(data.short_description) > 500:
            errors.append("La description courte ne peut pas dépasser 500 caractères")

        # Validation du SKU si fourni
        if data.sku is not None and len(data.sku) > 100:
            errors.append("Le SKU ne peut pas dépasser 100 caractères")

        # Validation des quantités si fournies
        if data.min_order_quantity is not None and data.min_order_quantity < 1:
            errors.append("La quantité minimum de commande doit être au moins 1")

        if data.stock_quantity is not None and data.stock_quantity < 0:
            errors.append("La quantité en stock ne peut pas être négative")

        # Validation de la devise si fournie
        if data.currency is not None and len(data.currency) != 3:
            errors.append("La devise doit être un code ISO à 3 lettres")

        return errors

    def _validate_delete_request(self, request: RequestBase[ProductSchema]) -> List[str]:
        """Valider la requête de suppression"""
        errors = []

        # Validation user_id
        if not request.user:
            errors.append("L'ID utilisateur est obligatoire")

        # Validation des données
        if not request.data:
            errors.append("Les données de la requête sont obligatoires")
            return errors

        data = request.data

        # Validation de l'ID
        if not data.id:
            errors.append("L'ID du produit est obligatoire")
        elif data.id <= 0:
            errors.append("L'ID du produit doit être positif")

        return errors