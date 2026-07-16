# ================================================
# app/routes/websocket_routes.py
# ================================================
"""
Routes WebSocket pour la messagerie en temps réel
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
import json

import jwt

from app.api.deps import get_db
from app.config.settings import settings
from app.websocket.connection_manager import manager
from app.services.messaging_service import MessagingService
from app.repositories.messaging_repo import ConversationRepository, MessageRepository, UserPresenceRepository
from app.repositories.user_repo import UserRepository
from app.core.logger import logger

from datetime import datetime

router = APIRouter(prefix="/ws", tags=["WebSocket"])


def _validate_ws_token(token: str, expected_user_id: int) -> bool:
    """
    Valide le JWT passé en query param pour une connexion WebSocket.

    Les WS ne passent pas par AuthMiddleware (scope HTTP uniquement), donc on
    valide ici. Vérifie aussi que le user_id du token correspond à celui de
    l'URL (anti-usurpation).
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.InvalidTokenError:
        return False
    token_user_id = payload.get("user_id")
    if token_user_id is None:
        return False
    try:
        return int(token_user_id) == expected_user_id
    except (TypeError, ValueError):
        return False


@router.websocket("/chat/{user_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        user_id: int,
        token: str = Query(...)  # Token d'authentification
):
    """
    WebSocket pour la messagerie en temps réel

    Format des messages:
    - Client → Serveur:
      {
        "type": "message",
        "conversation_id": 1,
        "content": "Hello!",
        "reply_to_message_id": null
      }

      {
        "type": "typing",
        "conversation_id": 1,
        "is_typing": true
      }

      {
        "type": "mark_read",
        "message_id": 123
      }

    - Serveur → Client:
      {
        "type": "new_message",
        "data": {...}
      }

      {
        "type": "typing_indicator",
        "conversation_id": 1,
        "user_name": "John Doe",
        "is_typing": true
      }

      {
        "type": "user_online",
        "user_id": 2,
        "is_online": true
      }
    """

    # Valider le token AVANT d'accepter la connexion
    if not _validate_ws_token(token, user_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning(f"WS refusé: token invalide pour user {user_id}")
        return

    await manager.connect(websocket, user_id)

    try:
        # Envoyer un message de bienvenue
        await websocket.send_json({
            "type": "connected",
            "message": f"Connecté en tant qu'utilisateur {user_id}",
            "user_id": user_id,
            "timestamp": str(datetime.now())
        })

        # Notifier les autres utilisateurs que cet utilisateur est en ligne
        await manager.broadcast({
            "type": "user_online",
            "user_id": user_id,
            "is_online": True
        })

        # Boucle d'écoute
        while True:
            # Recevoir un message du client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            message_type = message_data.get("type")

            if message_type == "ping":
                # Répondre au ping pour maintenir la connexion
                await websocket.send_json({"type": "pong"})

            elif message_type == "typing":
                # Indicateur de frappe
                conversation_id = message_data.get("conversation_id")
                is_typing = message_data.get("is_typing", True)

                # Diffuser aux autres participants de la conversation
                await manager.send_to_conversation(
                    {
                        "type": "typing_indicator",
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "is_typing": is_typing
                    },
                    conversation_id,
                    exclude_user_id=user_id
                )

            elif message_type == "subscribe":
                # S'abonner à une conversation
                conversation_id = message_data.get("conversation_id")
                manager.subscribe_to_conversation(conversation_id, user_id)

                await websocket.send_json({
                    "type": "subscribed",
                    "conversation_id": conversation_id
                })

            elif message_type == "unsubscribe":
                # Se désabonner d'une conversation
                conversation_id = message_data.get("conversation_id")
                manager.unsubscribe_from_conversation(conversation_id, user_id)

                await websocket.send_json({
                    "type": "unsubscribed",
                    "conversation_id": conversation_id
                })

            else:
                # Message non reconnu
                await websocket.send_json({
                    "type": "error",
                    "message": f"Type de message non reconnu: {message_type}"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"User {user_id} disconnected")

        # Notifier les autres utilisateurs
        await manager.broadcast({
            "type": "user_offline",
            "user_id": user_id,
            "is_online": False
        })

    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket)


@router.websocket("/notifications/{user_id}")
async def notifications_websocket(
        websocket: WebSocket,
        user_id: int,
        token: str = Query(...)
):
    """
    WebSocket dédié aux notifications en temps réel
    """
    if not _validate_ws_token(token, user_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning(f"WS notifications refusé: token invalide pour user {user_id}")
        return

    await manager.connect(websocket, user_id)

    try:
        await websocket.send_json({
            "type": "connected",
            "message": "Connecté au flux de notifications"
        })

        while True:
            # Maintenir la connexion ouverte
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"User {user_id} disconnected from notifications")

    except Exception as e:
        logger.error(f"Notifications WebSocket error: {e}")
        manager.disconnect(websocket)
