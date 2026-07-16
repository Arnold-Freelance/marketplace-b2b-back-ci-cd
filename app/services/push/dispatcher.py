"""
PushDispatcher — aiguille une notification vers les appareils d'un utilisateur.

Règles appliquées ici (cf. NOTIFICATIONS_V1.md §7) :
- pas de push si l'utilisateur a une connexion WebSocket vivante (§7.2) ;
- pas de push pour les types purement informatifs (§5) ;
- les `new_message` d'une même conversation sont regroupés via `collapse_id` (§7.3) ;
- un jeton rejeté `DeviceNotRegistered` est désactivé en base (§7.6).
"""
from typing import Optional

from app.core.enums import NotificationType
from app.core.logger import logger
from app.repositories.device_token_repo import DeviceTokenRepository
from app.schemas.notification import NotificationSchema
from app.services.push.provider import ExpoPushProvider, PushMessage, PushProviderBase
from app.websocket.connection_manager import manager

#: Types qui ne réveillent PAS le téléphone. Informatifs, consultables dans la
#: cloche : faire vibrer pour « il reste 4 unités » est un motif de désinstallation.
SILENT_NOTIFICATION_TYPES = frozenset({
    NotificationType.PRODUCT_LOW_STOCK,
    NotificationType.REVIEW_RECEIVED,
})


class PushDispatcher:
    """Envoie les notifications hors-app aux appareils enregistrés."""

    def __init__(
            self,
            device_repo: DeviceTokenRepository,
            provider: Optional[PushProviderBase] = None,
    ):
        self.device_repo = device_repo
        self.provider = provider or ExpoPushProvider()

    @staticmethod
    def _collapse_id(notification: NotificationSchema) -> Optional[str]:
        """Clé de regroupement — plusieurs messages d'un même fil = un seul push."""
        if notification.type == NotificationType.NEW_MESSAGE:
            conversation_id = (notification.data or {}).get("conversation_id")
            if conversation_id:
                return f"conversation:{conversation_id}"
        return None

    async def dispatch(self, notification: NotificationSchema) -> int:
        """Pousse la notification. Retourne le nombre d'appareils atteints."""
        if notification.type in SILENT_NOTIFICATION_TYPES:
            return 0

        # L'app est ouverte : la notification est déjà arrivée par WebSocket.
        if manager.is_online(notification.user_id):
            return 0

        devices = self.device_repo.get_active_tokens(notification.user_id)
        if not devices:
            return 0

        collapse_id = self._collapse_id(notification)
        messages = [
            PushMessage(
                token=device.token,
                title=notification.title,
                body=notification.message,
                # Le client s'en sert pour router vers le bon écran au tap.
                data={
                    "notification_id": notification.id,
                    "type": notification.type.value,
                    **(notification.data or {}),
                },
                collapse_id=collapse_id,
            )
            for device in devices
        ]

        result = await self.provider.send(messages)

        for token in result.invalid_tokens:
            self.device_repo.deactivate(token)
        if result.invalid_tokens:
            logger.info(f"{len(result.invalid_tokens)} jeton(s) push désactivé(s) (DeviceNotRegistered)")

        return result.delivered
