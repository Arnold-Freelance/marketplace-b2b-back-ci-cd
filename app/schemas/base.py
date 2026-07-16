from typing import Any, Dict, Optional, List, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict
from pydantic import model_serializer

T = TypeVar("T")

class RequestBase(BaseModel, Generic[T]):
    user_id: Optional[int] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
    user: Optional[int] = None
    data: Optional[T] = None
    datas: Optional[List[T]] = None

class ResponseBase(BaseModel, Generic[T]):
    success: bool
    message: str
    item: Optional[T] = None
    items: Optional[List[T]] = None
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    errors: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        from_attributes=True,
        #exclude_none=True  # Cette ligne fait tout le travail !
    )

    @model_serializer
    def serialize_model(self):
        # Exclut manuellement les valeurs None
        result = {}
        for field, value in self:
            if value is not None:
                result[field] = value
        return result