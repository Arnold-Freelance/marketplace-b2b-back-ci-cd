# app/repositories/product_repo.py
from typing import Optional, List, Tuple, Any, Dict
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, aliased
from app.repositories.base import BaseRepository
from app.models.product_entity import ProductEntity
from app.models.category_entity import CategoryEntity
from app.models.user_entity import UserEntity
from app.schemas.product import ProductSchema
from app.schemas.base import RequestBase


class ProductRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, ProductEntity)

    def get_by_sku(self, sku: str) -> Optional[ProductEntity]:
        """Récupérer un produit par son SKU"""
        return self.db.query(ProductEntity).filter(
            ProductEntity.sku == sku,
            ProductEntity.is_deleted == False
        ).first()

    def get_by_slug(self, slug: str) -> Optional[ProductEntity]:
        """Récupérer un produit par son slug"""
        return self.db.query(ProductEntity).filter(
            ProductEntity.slug == slug,
            ProductEntity.is_deleted == False
        ).first()

    def get_by_category_id(self, category_id: int) -> List[ProductEntity]:
        """Récupérer tous les produits d'une catégorie"""
        return self.db.query(ProductEntity).filter(
            ProductEntity.category_id == category_id,
            ProductEntity.is_deleted == False
        ).all()

    def get_by_supplier_id(self, supplier_id: int) -> List[ProductEntity]:
        """Récupérer tous les produits d'un fournisseur"""
        return self.db.query(ProductEntity).filter(
            ProductEntity.supplier_id == supplier_id,
            ProductEntity.is_deleted == False
        ).all()

    def count_by_category(self, category_id: int) -> int:
        """Compter les produits actifs (non supprimés) d'une catégorie."""
        return (
            self.db.query(func.count(ProductEntity.id))
            .filter(
                ProductEntity.category_id == category_id,
                ProductEntity.is_deleted == False,
                ProductEntity.is_active == True,
            )
            .scalar()
        ) or 0

    def get_showcase(self, limit: int = 10) -> List[ProductEntity]:
        """Vitrine de l'accueil : produits mis en avant d'abord, complétés par les
        plus consultés.

        Le tri fait tout le travail, en une seule requête : `is_featured DESC`
        remonte la curation en tête (True avant False), puis `views_count DESC`
        classe le reste par popularité. Pas de fusion ni de dédoublonnage à faire
        côté service — et le jour où un back-office marquera plus de produits,
        la vitrine se remplit de curation sans changer une ligne de code.

        La popularité est DÉRIVÉE de `views_count` (alimenté par
        `increment_views` à chaque consultation de fiche), jamais recopiée dans
        `is_featured` : un booléen figé mentirait dès la vue suivante.

        `created_at DESC` départage : au démarrage, quand presque tout est à zéro
        vue, la vitrine montre les nouveautés plutôt qu'un ordre arbitraire.
        """
        return (
            self.db.query(ProductEntity)
            .filter(
                ProductEntity.is_active == True,
                ProductEntity.is_deleted == False,
            )
            # `coalesce` obligatoire : `default=` est un défaut Python appliqué à
            # l'insertion par l'ORM, pas une contrainte de colonne — les lignes
            # antérieures peuvent être NULL (d'où le `or 0` d'`increment_views`).
            # Or en PostgreSQL, `ORDER BY ... DESC` remonte les NULL en PREMIER :
            # sans ça, un produit jamais vu coifferait la vitrine.
            .order_by(
                func.coalesce(ProductEntity.is_featured, False).desc(),
                func.coalesce(ProductEntity.views_count, 0).desc(),
                ProductEntity.created_at.desc(),
            )
            .limit(limit)
            .all()
        )

    def increment_views(self, product_id: int) -> None:
        """Incrémenter le compteur de vues"""
        product = self.get_by_id(product_id)
        if product:
            product.views_count = (product.views_count or 0) + 1
            self.db.commit()

    def update_stock(self, product_id: int, quantity: int) -> Optional[ProductEntity]:
        """Mettre à jour le stock d'un produit"""
        product = self.get_by_id(product_id)
        if product:
            product.stock_quantity = quantity
            self.db.commit()
            self.db.refresh(product)
        return product

    def _build_where_conditions(self, request: RequestBase[ProductSchema]) -> Tuple[List[Any], Dict[str, Any]]:
        """Construire les conditions WHERE pour les requêtes"""
        conditions = []
        params = {}

        # Alias pour les jointures
        category_alias = aliased(CategoryEntity)
        supplier_alias = aliased(UserEntity)
        params = {
            "category_alias": category_alias,
            "supplier_alias": supplier_alias
        }

        # Filtre par défaut : produits non supprimés
        conditions.append(ProductEntity.is_deleted == False)

        # Si pas de data, retourner les conditions par défaut
        if not request.data:
            return conditions, params

        filters = request.data

        # Filtres textuels avec LIKE (insensible à la casse)
        if filters.name:
            conditions.append(ProductEntity.name.ilike(f"%{filters.name}%"))

        if filters.slug:
            conditions.append(ProductEntity.slug.ilike(f"%{filters.slug}%"))

        if filters.sku:
            conditions.append(ProductEntity.sku.ilike(f"%{filters.sku}%"))

        if filters.description:
            conditions.append(ProductEntity.description.ilike(f"%{filters.description}%"))

        # Recherche globale
        if filters.search_query:
            search_condition = or_(
                ProductEntity.name.ilike(f"%{filters.search_query}%"),
                ProductEntity.slug.ilike(f"%{filters.search_query}%"),
                ProductEntity.description.ilike(f"%{filters.search_query}%"),
                ProductEntity.short_description.ilike(f"%{filters.search_query}%"),
                ProductEntity.sku.ilike(f"%{filters.search_query}%"),
                category_alias.name.ilike(f"%{filters.search_query}%")
            )
            conditions.append(search_condition)

        # Filtres exacts
        if filters.supplier_id is not None:
            conditions.append(ProductEntity.supplier_id == filters.supplier_id)

        if filters.category_id is not None:
            conditions.append(ProductEntity.category_id == filters.category_id)

        if filters.category_slug:
            conditions.append(category_alias.slug == filters.category_slug)

        if filters.currency:
            conditions.append(ProductEntity.currency == filters.currency)

        # Filtres de prix
        if filters.min_price is not None:
            conditions.append(ProductEntity.price >= filters.min_price)

        if filters.max_price is not None:
            conditions.append(ProductEntity.price <= filters.max_price)

        if filters.price is not None:
            conditions.append(ProductEntity.price == filters.price)

        # Filtre de stock
        if filters.in_stock is not None:
            if filters.in_stock:
                conditions.append(ProductEntity.stock_quantity > 0)
            else:
                conditions.append(ProductEntity.stock_quantity == 0)

        # Filtres booléens
        if filters.is_active is not None:
            conditions.append(ProductEntity.is_active == filters.is_active)

        if filters.is_featured is not None:
            conditions.append(ProductEntity.is_featured == filters.is_featured)

        if filters.is_deleted is not None:
            conditions = [c for c in conditions if 'is_deleted' not in str(c)]
            conditions.append(ProductEntity.is_deleted == filters.is_deleted)

        # Filtres de traçabilité
        # if filters.created_by is not None:
        #     conditions.append(ProductEntity.created_by == filters.created_by)
        #
        # if filters.updated_by is not None:
        #     conditions.append(ProductEntity.updated_by == filters.updated_by)

        return conditions, params

    def count(self, request: RequestBase[ProductSchema]) -> int:
        """Compter le nombre de produits selon les critères"""
        try:
            conditions, params = self._build_where_conditions(request)
            category_alias = params['category_alias']
            supplier_alias = params['supplier_alias']

            count_query = (
                self.db.query(func.count(ProductEntity.id))
                .outerjoin(category_alias, ProductEntity.category)
                .outerjoin(supplier_alias, ProductEntity.supplier)
            )

            if conditions:
                count_query = count_query.filter(and_(*conditions))

            total = count_query.scalar()
            return total if total else 0

        except Exception as e:
            print(f"Erreur lors du comptage des produits: {str(e)}")
            return 0

    def get_by_criteria(self, request: RequestBase[ProductSchema]) -> List[ProductEntity]:
        """Récupérer les produits selon les critères avec pagination"""
        try:
            conditions, params = self._build_where_conditions(request)
            category_alias = params['category_alias']
            supplier_alias = params['supplier_alias']

            query = (
                self.db.query(ProductEntity)
                .outerjoin(category_alias, ProductEntity.category)
                .outerjoin(supplier_alias, ProductEntity.supplier)
            )

            if conditions:
                query = query.filter(and_(*conditions))

            products = (
                query
                .order_by(ProductEntity.id.desc())
                .offset(request.offset)
                .limit(request.limit)
                .all()
            )

            return products if products else []

        except Exception as e:
            print(f"Erreur lors de la récupération des produits: {str(e)}")
            return []