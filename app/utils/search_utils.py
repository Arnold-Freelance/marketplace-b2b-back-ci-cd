from typing import List, Any, Dict, Tuple, Optional, Union, Type
from sqlalchemy import or_, and_, func, Column
from sqlalchemy.orm import aliased, joinedload, RelationshipProperty
from sqlalchemy.sql.sqltypes import String, Integer, Boolean, DateTime
from enum import Enum
import inspect

from app.models.category_entity import CategoryEntity


class FieldType(Enum):
    """Types de champs supportés"""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    FOREIGN_KEY = "foreign_key"
    RELATIONSHIP = "relationship"


class FilterOperator(Enum):
    """Opérateurs de filtrage"""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    LIKE = "like"
    ILIKE = "ilike"
    IN = "in"
    NOT_IN = "not_in"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    BETWEEN = "between"


class FieldConfig:
    """Configuration d'un champ"""

    def __init__(
            self,
            field_name: str,
            field_type: FieldType,
            column_attr: Any,
            operators: List[FilterOperator] = None,
            relationship_entity: Type = None,
            relationship_fields: List[str] = None,
            is_searchable: bool = True,
            is_filterable: bool = True
    ):
        self.field_name = field_name
        self.field_type = field_type
        self.column_attr = column_attr
        self.operators = operators or self._get_default_operators()
        self.relationship_entity = relationship_entity
        self.relationship_fields = relationship_fields or []
        self.is_searchable = is_searchable
        self.is_filterable = is_filterable

    def _get_default_operators(self) -> List[FilterOperator]:
        """Opérateurs par défaut selon le type"""
        defaults = {
            FieldType.STRING: [FilterOperator.EQUALS, FilterOperator.LIKE, FilterOperator.ILIKE, FilterOperator.IN],
            FieldType.INTEGER: [FilterOperator.EQUALS, FilterOperator.GT, FilterOperator.GTE, FilterOperator.LT,
                                FilterOperator.LTE, FilterOperator.IN],
            FieldType.BOOLEAN: [FilterOperator.EQUALS],
            FieldType.DATETIME: [FilterOperator.EQUALS, FilterOperator.GT, FilterOperator.GTE, FilterOperator.LT,
                                 FilterOperator.LTE, FilterOperator.BETWEEN],
            FieldType.FOREIGN_KEY: [FilterOperator.EQUALS, FilterOperator.IN, FilterOperator.IS_NULL],
            FieldType.RELATIONSHIP: [FilterOperator.EQUALS, FilterOperator.LIKE, FilterOperator.ILIKE]
        }
        return defaults.get(self.field_type, [FilterOperator.EQUALS])


class DynamicFilterBuilder:
    """Constructeur de filtres dynamiques"""

    def __init__(self, entity_class, session):
        self.entity_class = entity_class
        self.session = session
        self.field_configs = {}
        self.relationship_aliases = {}
        self.fixed_conditions = []

        # ✅ Initialiser les champs fixes
        self._setup_fixed_fields()

        # ✅ Découvrir automatiquement les champs
        self._auto_discover_fields()

    def _setup_fixed_fields(self):
        """Configure les champs fixes inchangés"""
        # ✅ Condition fixe : is_deleted = False par défaut
        self.add_fixed_condition(self.entity_class.is_deleted == False)

    def add_fixed_condition(self, condition):
        """Ajoute une condition fixe"""
        self.fixed_conditions.append(condition)

    def _auto_discover_fields(self):
        """Découvre automatiquement les champs de l'entité"""
        for attr_name in dir(self.entity_class):
            attr = getattr(self.entity_class, attr_name)

            # ✅ Colonnes normales
            if hasattr(attr, 'property') and hasattr(attr.property, 'columns'):
                column = attr.property.columns[0]
                field_type = self._get_field_type_from_column(column)

                self.field_configs[attr_name] = FieldConfig(
                    field_name=attr_name,
                    field_type=field_type,
                    column_attr=attr
                )

            # ✅ Relations
            elif hasattr(attr, 'property') and isinstance(attr.property, RelationshipProperty):
                self._setup_relationship_field(attr_name, attr)

    def _get_field_type_from_column(self, column) -> FieldType:
        """Détermine le type de champ à partir de la colonne SQLAlchemy"""
        if isinstance(column.type, String):
            return FieldType.STRING
        elif isinstance(column.type, Integer):
            if column.foreign_keys:
                return FieldType.FOREIGN_KEY
            return FieldType.INTEGER
        elif isinstance(column.type, Boolean):
            return FieldType.BOOLEAN
        elif isinstance(column.type, DateTime):
            return FieldType.DATETIME
        else:
            return FieldType.STRING  # Par défaut

    def _setup_relationship_field(self, attr_name: str, attr):
        """Configure un champ de relation"""
        relationship_entity = attr.property.mapper.class_

        # Créer l'alias pour cette relation
        alias = aliased(relationship_entity)
        self.relationship_aliases[attr_name] = alias

        # Champs de recherche par défaut dans la relation
        default_search_fields = []
        for field_name in ['name', 'title', 'label', 'slug']:
            if hasattr(relationship_entity, field_name):
                default_search_fields.append(field_name)

        self.field_configs[attr_name] = FieldConfig(
            field_name=attr_name,
            field_type=FieldType.RELATIONSHIP,
            column_attr=attr,
            relationship_entity=relationship_entity,
            relationship_fields=default_search_fields
        )

    def register_field(self, field_config: FieldConfig):
        """Enregistre manuellement un champ"""
        self.field_configs[field_config.field_name] = field_config

    def build_conditions(self, filters: Dict[str, Any]) -> Tuple[List[Any], Dict[str, Any]]:
        """Construit les conditions dynamiquement"""
        conditions = self.fixed_conditions.copy()
        params = {"aliases": self.relationship_aliases}

        for field_name, filter_value in filters.items():
            if field_name not in self.field_configs:
                continue

            field_config = self.field_configs[field_name]

            if not field_config.is_filterable:
                continue

            # ✅ Traitement selon le type de champ
            field_conditions = self._build_field_conditions(field_config, filter_value)
            if field_conditions:
                conditions.extend(field_conditions)

        return conditions, params

    def _build_field_conditions(self, field_config: FieldConfig, filter_value) -> List[Any]:
        """Construit les conditions pour un champ spécifique"""
        conditions = []

        if field_config.field_type == FieldType.STRING:
            conditions.extend(self._build_string_conditions(field_config, filter_value))
        elif field_config.field_type == FieldType.INTEGER:
            conditions.extend(self._build_integer_conditions(field_config, filter_value))
        elif field_config.field_type == FieldType.BOOLEAN:
            conditions.extend(self._build_boolean_conditions(field_config, filter_value))
        elif field_config.field_type == FieldType.FOREIGN_KEY:
            conditions.extend(self._build_foreign_key_conditions(field_config, filter_value))
        elif field_config.field_type == FieldType.RELATIONSHIP:
            conditions.extend(self._build_relationship_conditions(field_config, filter_value))
        elif field_config.field_type == FieldType.DATETIME:
            conditions.extend(self._build_datetime_conditions(field_config, filter_value))

        return conditions

    def _build_string_conditions(self, field_config: FieldConfig, filter_value) -> List[Any]:
        """Conditions pour champs string"""
        conditions = []

        if isinstance(filter_value, str):
            # Recherche ILIKE par défaut
            conditions.append(field_config.column_attr.ilike(f"%{filter_value}%"))
        elif isinstance(filter_value, list):
            # IN pour liste de valeurs
            conditions.append(field_config.column_attr.in_(filter_value))
        elif isinstance(filter_value, dict):
            # Filtrage avancé avec opérateur
            operator = filter_value.get('operator', 'ilike')
            value = filter_value.get('value')

            if operator == 'equals':
                conditions.append(field_config.column_attr == value)
            elif operator == 'ilike':
                conditions.append(field_config.column_attr.ilike(f"%{value}%"))
            elif operator == 'in':
                conditions.append(field_config.column_attr.in_(value))

        return conditions

    def _build_integer_conditions(self, field_config: FieldConfig, filter_value) -> List[Any]:
        """Conditions pour champs integer"""
        conditions = []

        if isinstance(filter_value, int):
            conditions.append(field_config.column_attr == filter_value)
        elif isinstance(filter_value, list):
            conditions.append(field_config.column_attr.in_(filter_value))
        elif isinstance(filter_value, dict):
            operator = filter_value.get('operator', 'equals')
            value = filter_value.get('value')

            if operator == 'equals':
                conditions.append(field_config.column_attr == value)
            elif operator == 'gt':
                conditions.append(field_config.column_attr > value)
            elif operator == 'gte':
                conditions.append(field_config.column_attr >= value)
            elif operator == 'lt':
                conditions.append(field_config.column_attr < value)
            elif operator == 'lte':
                conditions.append(field_config.column_attr <= value)
            elif operator == 'in':
                conditions.append(field_config.column_attr.in_(value))
            elif operator == 'between':
                min_val, max_val = value
                conditions.append(field_config.column_attr.between(min_val, max_val))

        return conditions

    def _build_boolean_conditions(self, field_config: FieldConfig, filter_value) -> List[Any]:
        """Conditions pour champs boolean"""
        if isinstance(filter_value, bool):
            return [field_config.column_attr == filter_value]
        return []

    def _build_foreign_key_conditions(self, field_config: FieldConfig, filter_value) -> List[Any]:
        """Conditions pour clés étrangères"""
        conditions = []

        if isinstance(filter_value, int):
            conditions.append(field_config.column_attr == filter_value)
        elif isinstance(filter_value, list):
            conditions.append(field_config.column_attr.in_(filter_value))
        elif filter_value is None:
            conditions.append(field_config.column_attr.is_(None))
        elif isinstance(filter_value, dict):
            operator = filter_value.get('operator', 'equals')
            value = filter_value.get('value')

            if operator == 'equals':
                conditions.append(field_config.column_attr == value)
            elif operator == 'in':
                conditions.append(field_config.column_attr.in_(value))
            elif operator == 'is_null':
                conditions.append(field_config.column_attr.is_(None))
            elif operator == 'is_not_null':
                conditions.append(field_config.column_attr.isnot(None))

        return conditions

    def _build_relationship_conditions(self, field_config: FieldConfig, filter_value) -> List[Any]:
        """Conditions pour relations"""
        conditions = []
        alias = self.relationship_aliases.get(field_config.field_name)

        if not alias:
            return conditions

        if isinstance(filter_value, str):
            # Recherche dans les champs de la relation
            relation_conditions = []
            for field_name in field_config.relationship_fields:
                if hasattr(alias, field_name):
                    attr = getattr(alias, field_name)
                    relation_conditions.append(attr.ilike(f"%{filter_value}%"))

            if relation_conditions:
                conditions.append(or_(*relation_conditions))

        return conditions

    def _build_datetime_conditions(self, field_config: FieldConfig, filter_value) -> List[Any]:
        """Conditions pour champs datetime"""
        conditions = []

        if isinstance(filter_value, dict):
            operator = filter_value.get('operator', 'equals')
            value = filter_value.get('value')

            if operator == 'equals':
                conditions.append(field_config.column_attr == value)
            elif operator == 'gt':
                conditions.append(field_config.column_attr > value)
            elif operator == 'gte':
                conditions.append(field_config.column_attr >= value)
            elif operator == 'lt':
                conditions.append(field_config.column_attr < value)
            elif operator == 'lte':
                conditions.append(field_config.column_attr <= value)
            elif operator == 'between':
                start_date, end_date = value
                conditions.append(field_config.column_attr.between(start_date, end_date))

        return conditions

    def build_search_conditions(self, search_query: str) -> List[Any]:
        """Construit les conditions de recherche globale"""
        if not search_query:
            return []

        search_conditions = []
        search_term = f"%{search_query}%"

        # ✅ Recherche dans les champs directs
        for field_config in self.field_configs.values():
            if not field_config.is_searchable:
                continue

            if field_config.field_type == FieldType.STRING:
                search_conditions.append(field_config.column_attr.ilike(search_term))
            elif field_config.field_type == FieldType.RELATIONSHIP:
                # Recherche dans les relations
                alias = self.relationship_aliases.get(field_config.field_name)
                if alias:
                    for field_name in field_config.relationship_fields:
                        if hasattr(alias, field_name):
                            attr = getattr(alias, field_name)
                            search_conditions.append(attr.ilike(search_term))

        return [or_(*search_conditions)] if search_conditions else []

    def build_query(self, filters: Dict[str, Any] = None, search_query: str = None):
        """Construit la requête complète avec JOINs"""
        query = self.session.query(self.entity_class)

        # ✅ Ajouter les JOINs nécessaires
        for relation_name, alias in self.relationship_aliases.items():
            relation_attr = getattr(self.entity_class, relation_name)
            # Déterminer la condition de JOIN
            if hasattr(relation_attr.property, 'local_columns'):
                local_col = list(relation_attr.property.local_columns)[0]
                remote_col = getattr(alias, 'id')  # Supposer que la clé primaire est 'id'
                query = query.outerjoin(alias, local_col == remote_col)

        # ✅ Appliquer les filtres
        all_conditions = []

        if filters:
            conditions, params = self.build_conditions(filters)
            all_conditions.extend(conditions)

        if search_query:
            search_conditions = self.build_search_conditions(search_query)
            all_conditions.extend(search_conditions)

        if all_conditions:
            query = query.filter(and_(*all_conditions))

        # ✅ Ajouter les options de chargement
        load_options = []
        for relation_name in self.relationship_aliases.keys():
            relation_attr = getattr(self.entity_class, relation_name)
            load_options.append(joinedload(relation_attr))

        if load_options:
            query = query.options(*load_options)

        return query


# ✅ Intégration avec votre système existant
class DynamicCategoryEntity(CategoryEntity):
    """Version dynamique de CategoryEntity"""

    def __init__(self):
        super().__init__()
        self.filter_builder = None

    def _get_filter_builder(self):
        """Initialise le constructeur de filtres"""
        if not self.filter_builder:
            self.filter_builder = DynamicFilterBuilder(CategoryEntity, self.db)

            # ✅ Configuration personnalisée des champs
            self._configure_custom_fields()

        return self.filter_builder

    def _configure_custom_fields(self):
        """Configuration personnalisée des champs"""
        builder = self.filter_builder

        # ✅ Configurer le champ parent
        if 'parent' in builder.field_configs:
            parent_config = builder.field_configs['parent']
            parent_config.relationship_fields = ['name', 'slug']
            parent_config.is_searchable = True

        # ✅ Désactiver la recherche sur certains champs sensibles
        if 'created_by' in builder.field_configs:
            builder.field_configs['created_by'].is_searchable = False

        if 'updated_by' in builder.field_configs:
            builder.field_configs['updated_by'].is_searchable = False

    def dynamic_search(self, filters: Dict[str, Any] = None, search_query: str = None, limit: int = 10,
                       offset: int = 0):
        """Recherche dynamique complète"""
        builder = self._get_filter_builder()

        # Construire la requête
        query = builder.build_query(filters, search_query)

        # Compter le total
        total = query.count()

        # Appliquer pagination et ordre
        results = query \
            .order_by(CategoryEntity.name.asc()) \
            .limit(limit) \
            .offset(offset) \
            .all()

        return {
            'items': results,
            'total': total,
            'limit': limit,
            'offset': offset
        }


# ✅ Exemples d'utilisation
def example_usage():
    """Exemples d'utilisation du système dynamique"""

    category = DynamicCategoryEntity()
    #category.db = session  # votre session

    # ✅ Exemple 1: Filtres simples
    filters = {
        'name': 'Tech',  # Recherche ILIKE
        'is_active': True,  # Booléen
        'parent_id': [1, 2, 3],  # Liste d'IDs
    }

    result1 = category.dynamic_search(filters=filters)
    print(f"Résultat 1: {len(result1['items'])} items")

    # ✅ Exemple 2: Filtres avancés avec opérateurs
    advanced_filters = {
        'name': {'operator': 'ilike', 'value': 'Tech'},
        'created_at': {'operator': 'gte', 'value': '2025-01-01'},
        'parent_id': {'operator': 'in', 'value': [1, 2, 3]},
        'parent': 'Electronics'  # Recherche dans la relation parent
    }

    result2 = category.dynamic_search(filters=advanced_filters)
    print(f"Résultat 2: {len(result2['items'])} items")

    # ✅ Exemple 3: Recherche globale
    result3 = category.dynamic_search(search_query="Tech")
    print(f"Résultat 3: {len(result3['items'])} items")

    # ✅ Exemple 4: Combinaison filtres + recherche
    result4 = category.dynamic_search(
        filters={'is_active': True},
        search_query="Tech",
        limit=20,
        offset=0
    )
    print(f"Résultat 4: {len(result4['items'])} items")


# ✅ Configuration pour différents types d'entités
class DynamicEntityFactory:
    """Factory pour créer des systèmes de filtrage pour différentes entités"""

    @staticmethod
    def create_filter_builder(entity_class, session, custom_config: Dict[str, Any] = None):
        """Crée un constructeur de filtres pour n'importe quelle entité"""
        builder = DynamicFilterBuilder(entity_class, session)

        if custom_config:
            # Appliquer la configuration personnalisée
            for field_name, config in custom_config.items():
                if field_name in builder.field_configs:
                    field_config = builder.field_configs[field_name]

                    # Mettre à jour les propriétés
                    for key, value in config.items():
                        setattr(field_config, key, value)

        return builder


# ✅ Test complet
def test_dynamic_system():
    """Test complet du système dynamique"""

    # Configuration pour CategoryEntity
    category_config = {
        'name': {'is_searchable': True, 'is_filterable': True},
        'slug': {'is_searchable': True, 'is_filterable': True},
        'description': {'is_searchable': True, 'is_filterable': True},
        'parent': {
            'is_searchable': True,
            'relationship_fields': ['name', 'slug']
        },
        'created_by': {'is_searchable': False},  # Champ sensible
        'updated_by': {'is_searchable': False},  # Champ sensible
    }

    builder = DynamicEntityFactory.create_filter_builder(
        CategoryEntity,
        session,
        category_config
    )

    # Test avec différents types de filtres
    test_filters = {
        'name': 'Tech',
        'is_active': True,
        'parent_id': {'operator': 'in', 'value': [1, 2, 3]},
        'created_at': {'operator': 'gte', 'value': '2025-01-01'}
    }

    query = builder.build_query(test_filters, "Electronics")
    results = query.all()

    print(f"Test réussi: {len(results)} résultats trouvés")

    return len(results) > 0