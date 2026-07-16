"""
Routes messagerie — conversations + messages (REST idiomatique).

- POST /api/v1/conversations                    créer/récupérer une conversation
- GET  /api/v1/conversations                    mes conversations
- GET  /api/v1/conversations/{id}/messages      messages d'une conversation
- POST /api/v1/messages                          envoyer un message
- PUT  /api/v1/messages/{id}/read                marquer un message comme lu

Le temps réel passe par le WebSocket (/ws/chat/{user_id}). Ces routes REST
sont le fallback / l'historique persistant.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.repositories.device_token_repo import DeviceTokenRepository
from app.repositories.messaging_repo import (
    ConversationRepository,
    MessageRepository,
    UserPresenceRepository,
)
from app.repositories.notification_repo import NotificationRepository
from app.repositories.user_repo import UserRepository
from app.schemas.base import ResponseBase
from app.schemas.messaging import (
    ConversationCreateSchema,
    ConversationSchema,
    CreateMessageSchema,
    MessageSchema,
)
from app.services.messaging_service import MessagingService
from app.services.notification_service import NotificationService
from app.services.push.dispatcher import PushDispatcher

router = APIRouter(prefix="/api/v1", tags=["Messaging"])


def get_messaging_service(db: Session = Depends(get_db)) -> MessagingService:
    return MessagingService(
        ConversationRepository(db),
        MessageRepository(db),
        UserRepository(db),
        UserPresenceRepository(db),
        # Sans ce service, le message part mais le destinataire hors-app n'en
        # sait rien : ni notification en base, ni push.
        notification_service=NotificationService(
            NotificationRepository(db),
            push_dispatcher=PushDispatcher(DeviceTokenRepository(db)),
            conversation_repo=ConversationRepository(db),
        ),
    )


@router.post(
    "/conversations",
    response_model=ResponseBase[ConversationSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_or_get_conversation(
    data: ConversationCreateSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[MessagingService, Depends(get_messaging_service)],
):
    """Crée une conversation avec un autre utilisateur (ou récupère l'existante)."""
    return service.get_or_create_conversation(user_id, data)


@router.get("/conversations", response_model=ResponseBase[ConversationSchema])
async def list_my_conversations(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[MessagingService, Depends(get_messaging_service)],
):
    """Mes conversations, triées par dernière activité."""
    return service.get_my_conversations(user_id)


@router.get("/conversations/{conversation_id}", response_model=ResponseBase[ConversationSchema])
async def get_conversation(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[MessagingService, Depends(get_messaging_service)],
    conversation_id: int = Path(..., gt=0),
):
    """Détail d'une conversation (réservée à ses participants)."""
    return service.get_conversation(user_id, conversation_id)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ResponseBase[MessageSchema],
)
async def list_conversation_messages(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[MessagingService, Depends(get_messaging_service)],
    conversation_id: int = Path(..., gt=0),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Messages d'une conversation (marque les non-lus comme lus au passage)."""
    return service.get_conversation_messages(user_id, conversation_id, limit, offset)


@router.post(
    "/messages",
    response_model=ResponseBase[MessageSchema],
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    data: CreateMessageSchema,
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[MessagingService, Depends(get_messaging_service)],
):
    """Envoie un message (persistant + broadcast WebSocket au destinataire)."""
    return await service.send_message(user_id, data)


@router.put("/messages/{message_id}/read", response_model=ResponseBase[MessageSchema])
async def mark_message_read(
    user_id: Annotated[int, Depends(get_current_user)],
    service: Annotated[MessagingService, Depends(get_messaging_service)],
    message_id: int = Path(..., gt=0),
):
    """Marque un message reçu comme lu (notifie l'expéditeur via WebSocket)."""
    return await service.mark_as_read(user_id, message_id)
