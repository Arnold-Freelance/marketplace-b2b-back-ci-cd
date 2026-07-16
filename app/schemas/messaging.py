# app/schemas/messaging.py
"""
Schémas pour la messagerie
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.schema_base import SchemaBase


class ConversationSchema(SchemaBase):
    """Schéma pour une conversation"""
    id: Optional[int] = None
    buyer_id: Optional[int] = None
    supplier_id: Optional[int] = None
    order_id: Optional[int] = None
    product_id: Optional[int] = None
    subject: Optional[str] = None
    is_active: bool = True
    is_archived: bool = False

    last_message_at: Optional[str] = None
    last_message_preview: Optional[str] = None

    unread_count_buyer: int = 0
    unread_count_supplier: int = 0
    unread_count: Optional[int] = 0  # Pour l'utilisateur actuel

    # Informations enrichies
    other_user_id: Optional[int] = None
    other_user_name: Optional[str] = None
    other_user_avatar: Optional[str] = None
    other_user_is_online: Optional[bool] = False

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConversationCreateSchema(BaseModel):
    """Schéma pour créer/récupérer une conversation"""
    other_user_id: int = Field(..., gt=0)
    order_id: Optional[int] = Field(None, gt=0)
    product_id: Optional[int] = Field(None, gt=0)
    subject: Optional[str] = Field(None, max_length=255)


class MessageSchema(SchemaBase):
    """Schéma pour un message"""
    id: Optional[int] = None
    conversation_id: Optional[int] = None
    sender_id: Optional[int] = None
    content: str
    attachments: Optional[List[Dict[str, Any]]] = []
    status: Optional[str] = "sent"
    is_read: bool = False
    read_at: Optional[str] = None
    reply_to_message_id: Optional[int] = None
    is_system_message: bool = False

    # Informations enrichies
    sender_name: Optional[str] = None
    sender_avatar: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CreateMessageSchema(BaseModel):
    """Schéma pour créer un message"""
    conversation_id: int = Field(..., gt=0)
    content: str = Field(..., min_length=1, max_length=5000)
    attachments: Optional[List[Dict[str, Any]]] = []
    reply_to_message_id: Optional[int] = Field(None, gt=0)