# ================================================
# app/schemas/notification.py
# ================================================
"""
Schémas pour les notifications
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.schema_base import SchemaBase
from app.core.enums import DevicePlatform, PushProvider
from app.models.messaging_entity import NotificationType


class NotificationSchema(SchemaBase):
    """Schéma pour une notification"""
    id: Optional[int] = None
    user_id: Optional[int] = None
    type: NotificationType
    title: str
    message: str
    data: Optional[Dict[str, Any]] = {}
    is_read: bool = False
    read_at: Optional[str] = None
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None


class CreateNotificationSchema(BaseModel):
    """Schéma pour créer une notification"""
    user_id: int
    type: NotificationType
    title: str
    message: str
    data: Optional[Dict[str, Any]] = {}
    action_url: Optional[str] = None
    action_label: Optional[str] = None


class RegisterDeviceSchema(BaseModel):
    """Corps de `POST /notifications/devices`."""
    token: str = Field(..., min_length=8, max_length=255)
    platform: DevicePlatform
    provider: PushProvider = PushProvider.EXPO
    device_id: Optional[str] = Field(None, max_length=128)


class DeviceTokenSchema(SchemaBase):
    """Jeton push enregistré."""
    id: Optional[int] = None
    user_id: Optional[int] = None
    token: str
    platform: DevicePlatform
    provider: PushProvider
    device_id: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None


class NotificationSummarySchema(BaseModel):
    """Compteurs alimentant les pastilles de l'app (cf. NOTIFICATIONS_V1.md §6).

    Le panier n'y figure pas : il est connu localement par le client.
    """
    messages: int = 0
    orders: int = 0
    bell: int = 0
    total: int = 0