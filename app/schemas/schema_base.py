from pydantic import BaseModel, ConfigDict, model_serializer
from typing import Optional


class MyBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_serializer
    def serialize_model(self):
        # Exclut manuellement les valeurs None
        result = {}
        for field, value in self:
            if value is not None:
                result[field] = value
        return result


class SchemaBase(MyBase):
    search_query: Optional[str] = None

    #Champ d'audit
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: Optional[str] = None  # Format dd/MM/yyyy
    updated_at: Optional[str] = None  # Format dd/MM/yyyy
    is_deleted: Optional[bool] = False




