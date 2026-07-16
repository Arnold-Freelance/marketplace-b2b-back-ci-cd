"""
Routes notifications (REST idiomatique).

- GET /api/v1/notifications                  mes notifications (filtre unread_only)
- PUT /api/v1/notifications/{id}/read        marquer une notification comme lue
- PUT /api/v1/notifications/read-all         tout marquer comme lu

Les notifications sont créées par les services métier (commandes, messages…)
via les helpers `notify_*` de NotificationService, pas par une route directe.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_current_user, get_db
from app.repositories.device_token_repo import DeviceTokenRepository
from app.repositories.messaging_repo import ConversationRepository
from app.repositories.notification_repo import NotificationRepository
from app.schemas.base import ResponseBase
from app.schemas.notification import (
    DeviceTokenSchema,
    NotificationSchema,
    NotificationSummarySchema,
    RegisterDeviceSchema,
)
from app.services.device_token_service import DeviceTokenService
from app.services.notification_service import NotificationService
from app.services.push.dispatcher import PushDispatcher
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(
        NotificationRepository(db),
        push_dispatcher=PushDispatcher(DeviceTokenRepository(db)),
        conversation_repo=ConversationRepository(db),
    )


def get_device_token_service(db: Session = Depends(get_db)) -> DeviceTokenService:
    return DeviceTokenService(DeviceTokenRepository(db))


@router.get("", response_model=ResponseBase[NotificationSchema])
async def list_my_notifications(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    unread_only: bool = Query(False, description="Ne renvoyer que les non-lues"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Mes notifications. `unread_count` dans metadata."""
    return service.get_my_notifications(user_id, unread_only, limit, offset)


@router.get("/summary", response_model=ResponseBase[NotificationSummarySchema])
async def get_notifications_summary(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    role: str | None = Query(None, pattern="^(buyer|supplier)$", description="Restreint au périmètre de l'espace actif"),
):
    """Compteurs des pastilles (messages, commandes, cloche)."""
    return service.get_summary(user_id, role=role)


@router.post("/devices", response_model=ResponseBase[DeviceTokenSchema], status_code=201)
async def register_device(
    data: RegisterDeviceSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[DeviceTokenService, Depends(get_device_token_service)],
):
    """Enregistre le jeton push de l'appareil courant."""
    return service.register(user_id, data)


@router.delete("/devices/{token}", response_model=ResponseBase[DeviceTokenSchema])
async def unregister_device(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[DeviceTokenService, Depends(get_device_token_service)],
    token: str = Path(..., min_length=8, max_length=255),
):
    """Désenregistre l'appareil. À appeler au logout."""
    return service.unregister(user_id, token)


@router.put("/read-all", response_model=ResponseBase[NotificationSchema])
async def mark_all_notifications_read(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    category: str | None = Query(None, pattern="^orders$", description="Ne vider que ce badge"),
):
    """Marque mes notifications comme lues (toutes, ou une seule catégorie)."""
    return service.mark_all_as_read(user_id, category=category)


@router.put("/{notification_id}/read", response_model=ResponseBase[NotificationSchema])
async def mark_notification_read(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    notification_id: int = Path(..., gt=0),
):
    """Marque une notification comme lue."""
    return service.mark_as_read(user_id, notification_id)


@router.delete("/{notification_id}", response_model=ResponseBase[NotificationSchema])
async def delete_notification(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    notification_id: int = Path(..., gt=0),
):
    """Supprime une notification (réservée à son propriétaire)."""
    return service.delete_notification(user_id, notification_id)
