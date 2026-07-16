from typing import Optional, List
from app.schemas.schema_base import SchemaBase


class CategorySchema(SchemaBase):
    id: Optional[int] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    parent_id: Optional[int] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    is_active: Optional[bool] = True

    # Nombre de produits actifs dans la catégorie (calculé)
    product_count: Optional[int] = None

    # Relations parent
    parent_name: Optional[str] = None
    parent_slug: Optional[str] = None

    # Relations enfants (optionnel)
    children: Optional[List['CategorySchema']] = None

