from typing import List

from sqlalchemy.exc import IntegrityError

from app.mappers.category_mapper import CategoryMapper
from app.repositories.category_repo import CategoryRepo
from app.repositories.product_repo import ProductRepository
from app.schemas.category import CategorySchema
from app.schemas.base import RequestBase, ResponseBase


class CategoryService:

    def __init__(self, category_repo: CategoryRepo, product_repo: ProductRepository):
        self.category_repo = category_repo
        self.product_repo = product_repo

    def create(self, request: RequestBase[CategorySchema]) -> ResponseBase[CategorySchema]:
        """Créer une nouvelle catégorie avec validation complète"""

        # Validation des données d'entrée
        validation_errors = self._validate_create_request(request)
        if validation_errors:
            return ResponseBase[CategorySchema](
                success=False,
                message="Erreurs de validation",
                errors=validation_errors
            )

        try:
            # Vérifier si une catégorie avec le même nom existe déjà
            existing_category = self.category_repo.get_by_name(request.data.name)
            if existing_category:
                return ResponseBase[CategorySchema](
                    success=False,
                    message=f"Une catégorie avec le nom '{request.data.name}' existe déjà"
                )

            # Préparer les données pour la création
            category_data = request.data.model_dump(exclude_none=True)
            category_data['created_by'] = request.user  # Ajouter l'ID utilisateur

            # Créer la catégorie
            new_category = self.category_repo.create(**category_data)

            # Convertir en schema pour la réponse
            #category_schema = CategorySchema.model_validate(new_category)
            category_schema = CategoryMapper.entity_to_schema(new_category)

            return ResponseBase[CategorySchema](
                success=True,
                message="Catégorie créée avec succès",
                item=category_schema.model_dump(exclude_none=True)
            )

        except IntegrityError:
            return ResponseBase[CategorySchema](
                success=False,
                message="Erreur d'intégrité de données (nom déjà existant ou contrainte violée)"
            )

        except Exception as e:
            print(f"Erreur inattendue lors de la création de catégorie: {e}")
            return ResponseBase[CategorySchema](
                success=False,
                message="Erreur interne lors de la création de la catégorie"
            )

    def _validate_create_request(self, request: RequestBase[CategorySchema]) -> List[str]:
        """Valider la requête de création"""
        errors = []

        # Validation user_id
        if not request.user:
            errors.append("L'ID utilisateur est obligatoire")

        # Validation des données
        if not request.data:
            errors.append("Les données de la catégorie sont obligatoires")
            return errors

        data = request.data

        # Validation du nom
        if not data.name or not data.name.strip():
            errors.append("Le nom de la catégorie est obligatoire")
        elif len(data.name.strip()) < 2:
            errors.append("Le nom de la catégorie doit contenir au moins 2 caractères")
        elif len(data.name.strip()) > 100:
            errors.append("Le nom de la catégorie ne peut pas dépasser 100 caractères")

        return errors

    def update(self, request: RequestBase[CategorySchema]) -> ResponseBase[CategorySchema]:
        validation_errors = self._validate_update_request(request)
        if validation_errors:
            return ResponseBase[CategorySchema](
                success=False,
                message="Erreurs de validation",
                errors=validation_errors
            )
        data = request.data
        existing_category = self.category_repo.get_by_id(data.id)
        if not existing_category:
            return ResponseBase[CategorySchema](
                success=False,
                message= "L'id de la categorie n'exite pas"
            )
        if data.parent_id:
            existing_parent = self.category_repo.get_by_id(data.parent_id)
            if not existing_parent:
                return ResponseBase[CategorySchema](
                    success=False,
                    message= "L'id de la parent n'existe pas"
                )

        if data.name:
            existing_category.name = data.name
        if data.slug:
            existing_category.slug = data.slug
        if data.description:
            existing_category.description = data.description
        if data.is_active:
            existing_category.is_active = data.is_active

        category_saved = self.category_repo.update(existing_category.id, existing_category)
        category_schema = CategoryMapper.entity_to_schema(category_saved)
        return ResponseBase[CategorySchema](
            success=True,
            message="Opération réussie avec succès",
            item= category_schema
        )


    def _validate_update_request(self, request: RequestBase[CategorySchema]) -> List[str]:
        errors = []
        if not request.user:
            errors.append("L'ID utilisateur est obligatoire")

        if not request.data:
            errors.append("La requete attendue n'est pas fournie")
            return errors

        data = request.data
        if not data.id:
            errors.append("Id de la categoriee est est obligatoire")

        return errors

    def delete(self, request: RequestBase[CategorySchema]) -> ResponseBase[CategorySchema]:
        validation_errors = self._validate_delete_request(request)
        if validation_errors:
            return ResponseBase[CategorySchema](
                success=False,
                message="Erreurs de validation",
                errors=validation_errors
            )
        data = request.data
        existing_category = self.category_repo.get_by_id(data.id)
        if not existing_category:
            return ResponseBase[CategorySchema](
                success=False,
                message= "L'id de la categorie n'exite pas"
            )

        existing_children = self.category_repo.get_by_parent_id(data.id)
        if existing_children:
            return ResponseBase[CategorySchema](
                success=False,
                message= "Cette categorie est parent d'autres categories"
            )

        existing_products = self.product_repo.get_by_category_id(data.id)
        if existing_products:
            return ResponseBase[CategorySchema](
                success=False,
                message= "Cette categorie est associée à des products"
            )

        self.category_repo.delete(existing_category.id)
        return ResponseBase[CategorySchema](
            success=True,
            message= "L'id de la categorie n'exite pas"
        )




    def _validate_delete_request(self, request: RequestBase[CategorySchema]) -> List[str]:
        errors = []
        if not request.user:
            errors.append("L'ID utilisateur est obligatoire")

        if not request.data:
            errors.append("La requete attendue n'est pas fournie")
            return errors
        data = request.data
        if not data.id:
            errors.append("Id de la categoriee est est obligatoire")

        return errors

    def get_by_criteria(self, request: RequestBase[CategorySchema]) -> ResponseBase[CategorySchema]:
        try:
            # Récupérer le count en premier
            count = self.category_repo.count(request)

            if count == 0:
                return ResponseBase(
                    success=True,
                    message="Liste vide: Aucune catégorie trouvée",
                )

            # Récupérer les données
            categories = self.category_repo.get_by_criteria(request)

            # Convertir les CategoryEntity en CategorySchema avec le mapper
            categories_schema = CategoryMapper.entities_to_schemas(categories)
            items = []
            for categoru_schema in categories_schema:
                categoru_schema = self.get_full_infos(categoru_schema)
                items.append(categoru_schema)

            return ResponseBase(
                success=True,
                message="Opération réussie avec succès",
                items=items,
                total=count,
                limit=request.limit,
                offset=request.offset
            )

        except Exception as e:
            return ResponseBase(
                success=False,
                message="Erreur lors de la récupération des catégories",
                errors=[str(e)]
            )

    def get_full_infos(self, data: CategorySchema) -> CategorySchema:
        children = self.category_repo.get_by_parent_id(data.id)
        if children:
            data.children = CategoryMapper.entities_to_schemas(children)
        return data
