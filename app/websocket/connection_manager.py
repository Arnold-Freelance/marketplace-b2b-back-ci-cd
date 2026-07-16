# ================================================
# app/websocket/connection_manager.py
# ================================================
"""
Gestionnaire de connexions WebSocket
"""
from typing import Dict, Set, List, Optional
from fastapi import WebSocket
from datetime import datetime
import json
import asyncio


class ConnectionManager:
    """Gestionnaire centralisé des connexions WebSocket"""

    def __init__(self):
        # user_id -> Set[WebSocket]
        self.active_connections: Dict[int, Set[WebSocket]] = {}

        # conversation_id -> Set[user_id]
        self.conversation_subscribers: Dict[int, Set[int]] = {}

        # websocket -> user_id
        self.websocket_to_user: Dict[WebSocket, int] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """Accepter une nouvelle connexion"""
        await websocket.accept()

        # Ajouter la connexion
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)
        self.websocket_to_user[websocket] = user_id

        print(f"✅ User {user_id} connected. Total connections: {len(self.active_connections[user_id])}")

    def disconnect(self, websocket: WebSocket):
        """Déconnecter un utilisateur"""
        user_id = self.websocket_to_user.get(websocket)

        if user_id and user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

            # Nettoyer si plus de connexions
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

            del self.websocket_to_user[websocket]

            print(f"❌ User {user_id} disconnected")

    def is_online(self, user_id: int) -> bool:
        """L'utilisateur a-t-il au moins une connexion WebSocket vivante ?

        Sert d'aiguillage au push : si l'app est ouverte, la notification arrive
        déjà en temps réel et un push ferait doublon.
        """
        return bool(self.active_connections.get(user_id))

    async def send_personal_message(self, message: dict, user_id: int):
        """Envoyer un message à un utilisateur spécifique"""
        if user_id in self.active_connections:
            # Envoyer à toutes les connexions de l'utilisateur
            disconnected = set()

            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    print(f"Error sending to user {user_id}: {e}")
                    disconnected.add(websocket)

            # Nettoyer les connexions mortes
            for websocket in disconnected:
                self.disconnect(websocket)

    async def send_to_conversation(self, message: dict, conversation_id: int, exclude_user_id: Optional[int] = None):
        """Envoyer un message à tous les participants d'une conversation"""
        if conversation_id in self.conversation_subscribers:
            for user_id in self.conversation_subscribers[conversation_id]:
                if exclude_user_id and user_id == exclude_user_id:
                    continue

                await self.send_personal_message(message, user_id)

    async def broadcast(self, message: dict):
        """Diffuser un message à tous les utilisateurs connectés"""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)

    def subscribe_to_conversation(self, conversation_id: int, user_id: int):
        """Abonner un utilisateur à une conversation"""
        if conversation_id not in self.conversation_subscribers:
            self.conversation_subscribers[conversation_id] = set()

        self.conversation_subscribers[conversation_id].add(user_id)

    def unsubscribe_from_conversation(self, conversation_id: int, user_id: int):
        """Désabonner un utilisateur d'une conversation"""
        if conversation_id in self.conversation_subscribers:
            self.conversation_subscribers[conversation_id].discard(user_id)

            # Nettoyer si plus d'abonnés
            if not self.conversation_subscribers[conversation_id]:
                del self.conversation_subscribers[conversation_id]

    def is_user_online(self, user_id: int) -> bool:
        """Vérifier si un utilisateur est en ligne"""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

    def get_online_users_count(self) -> int:
        """Obtenir le nombre d'utilisateurs en ligne"""
        return len(self.active_connections)


# Instance globale
manager = ConnectionManager()