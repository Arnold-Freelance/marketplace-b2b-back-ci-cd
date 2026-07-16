from typing import Optional, List, Tuple, Any, Dict
from sqlalchemy import and_, or_, func, text
from sqlalchemy.orm import Session, aliased, joinedload

from app.models.category_entity import CategoryEntity
from app.repositories.base import BaseRepository
from app.schemas.category import CategorySchema
from app.schemas.base import RequestBase, ResponseBase


class CategoryRepo(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db, CategoryEntity)

    # def get_by_id(self, id: int) -> Optional[CategoryEntity]:
    #     return self.db.query(CategoryEntity).filter(CategoryEntity.id == id).first()

    def get_by_parent_id(self, parent_id: int) -> Optional[List[CategoryEntity]]:
        return self.db.query(CategoryEntity).filter(CategoryEntity.parent_id == parent_id).all()

    def get_by_slug(self, slug: str) -> Optional[CategoryEntity]:
        return self.db.query(CategoryEntity).filter(CategoryEntity.slug == slug).first()

    def get_by_name(self, name: str) -> Optional[CategoryEntity]:
        return self.db.query(CategoryEntity).filter(CategoryEntity.name == name).first()

    def get_by_description(self, description: str) -> Optional[CategoryEntity]:
        return self.db.query(CategoryEntity).filter(CategoryEntity.description == description).first()

    def _build_where_conditions(self, request: RequestBase[CategorySchema]) -> Tuple[List[Any], Dict[str, Any]]:
        conditions = []
        params = {}

        #Parent category
        parent_category = aliased(CategoryEntity)
        params = {"parent_alias": parent_category}

        # Filtres par défaut
        conditions.append(CategoryEntity.is_deleted == False)

        # Si pas de data, retourner les conditions par défaut
        if not request.data:
            return conditions, params

        filters = request.data

        # Filtres textuels avec LIKE (insensible à la casse)
        if filters.name:
            conditions.append(CategoryEntity.name.ilike(f"%{filters.name}%"))

        if filters.slug:
            conditions.append(CategoryEntity.slug.ilike(f"%{filters.slug}%"))

        if filters.description:
            conditions.append(CategoryEntity.description.ilike(f"%{filters.description}%"))

        # Recherche globale dans plusieurs champs
        if filters.search_query:
            search_condition = or_(
                CategoryEntity.name.ilike(f"%{filters.search_query}%"),
                CategoryEntity.slug.ilike(f"%{filters.search_query}%"),
                CategoryEntity.description.ilike(f"%{filters.search_query}%"),

                parent_category.name.ilike(f"%{filters.search_query}%"),
                parent_category.slug.ilike(f"%{filters.search_query}%")
            )
            conditions.append(search_condition)

        # Filtres exacts
        if filters.parent_id is not None:
            conditions.append(CategoryEntity.parent_id == filters.parent_id)

        if filters.created_by is not None:
            conditions.append(CategoryEntity.created_by == filters.created_by)

        if filters.updated_by is not None:
            conditions.append(CategoryEntity.updated_by == filters.updated_by)

        # Filtres booléens
        if filters.is_active is not None:
            conditions.append(CategoryEntity.is_active == filters.is_active)

        if filters.is_deleted is not None:
            # Remplacer la condition par défaut si spécifiée
            conditions = [c for c in conditions if not str(c).startswith('categories.is_deleted')]
            conditions.append(CategoryEntity.is_deleted == filters.is_deleted)

        return conditions, params

    def count(self, request: RequestBase[CategorySchema]) -> int:
        try:
            # Construire les conditions WHERE
            conditions, params = self._build_where_conditions(request)
            parent_category = params['parent_alias']


            # Query de comptage
            count_query = self.db.query(func.count(CategoryEntity.id)).outerjoin(parent_category, CategoryEntity.parent)

            # Appliquer tous les filtres
            if conditions:
                count_query = count_query.filter(and_(*conditions))

            # Exécuter et retourner le résultat
            total = count_query.scalar()
            print("Total category:", total)
            return total if total else 0

        except Exception as e:
            print(f"Erreur lors du comptage: {str(e)}")
            return 0

    def get_by_criteria(self, request: RequestBase[CategorySchema]) -> List[CategoryEntity]:
        try:
            # Construire les conditions WHERE une seule fois
            conditions, params = self._build_where_conditions(request)
            parent_category = params['parent_alias']

            # Base query pour les données
            #query = self.db.query(CategoryEntity)
            query = self.db.query(CategoryEntity).outerjoin(parent_category, CategoryEntity.parent)

            # Appliquer tous les filtres
            if conditions:
                query = query.filter(and_(*conditions))

            # Appliquer l'ordre et la pagination
            categories = (query
                          .order_by(CategoryEntity.id.desc())
                          .offset(request.offset)
                          .limit(request.limit)
                          .all())

            return categories if categories else []
        except Exception as e:
            print(f"Erreur lors de la récupération: {str(e)}")
            return []


