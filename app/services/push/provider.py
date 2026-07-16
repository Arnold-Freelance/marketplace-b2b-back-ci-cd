"""
Adaptateur d'envoi push — abstrait pour permettre la bascule Expo → FCM direct.

Le choix retenu pour la v1 est Expo Push (cf. NOTIFICATIONS_V1.md §3). L'entité
`DeviceTokenEntity.provider` porte le relais, si bien qu'ajouter FCM revient à
écrire un second `PushProvider` et à router dessus — sans migration de données.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from app.core.logger import logger

#: Endpoint public du relais Expo. Aucun secret requis tant que le projet Expo
#: n'active pas « Enhanced Security » (auquel cas un access token est à ajouter).
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

#: Expo accepte jusqu'à 100 messages par requête.
EXPO_BATCH_SIZE = 100


@dataclass
class PushMessage:
    """Un push à destination d'un appareil."""
    token: str
    title: str
    body: str
    data: Dict[str, Any] = field(default_factory=dict)
    #: Regroupe les pushs de même clé (ex. `conversation:12`) — cf. règle métier §7.3.
    collapse_id: Optional[str] = None


@dataclass
class PushResult:
    """Issue d'un envoi, du point de vue de l'appelant."""
    delivered: int = 0
    #: Jetons rejetés définitivement par le relais → à désactiver en base.
    invalid_tokens: List[str] = field(default_factory=list)


class PushProviderBase(ABC):
    """Contrat d'un relais push."""

    @abstractmethod
    async def send(self, messages: List[PushMessage]) -> PushResult:
        ...


class ExpoPushProvider(PushProviderBase):
    """Relais Expo Push Service (→ FCM sur Android, APNs sur iOS)."""

    def __init__(self, timeout: float = 10.0, access_token: Optional[str] = None):
        self.timeout = timeout
        self.access_token = access_token

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    @staticmethod
    def _to_payload(message: PushMessage) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "to": message.token,
            "title": message.title,
            "body": message.body,
            "data": message.data,
            "sound": "default",
            "priority": "high",
            # Android : ouvre l'app sur le tap plutôt que d'empiler des notifs muettes.
            "channelId": "default",
        }
        if message.collapse_id:
            payload["collapseId"] = message.collapse_id
        return payload

    async def send(self, messages: List[PushMessage]) -> PushResult:
        result = PushResult()
        if not messages:
            return result

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for start in range(0, len(messages), EXPO_BATCH_SIZE):
                batch = messages[start:start + EXPO_BATCH_SIZE]
                payload = [self._to_payload(m) for m in batch]

                try:
                    response = await client.post(EXPO_PUSH_URL, json=payload, headers=self._headers())
                    response.raise_for_status()
                    tickets = response.json().get("data", [])
                except Exception as exc:
                    # Un relais injoignable ne doit jamais casser le flux métier :
                    # la notification est déjà persistée et visible en in-app.
                    logger.error(f"Expo push: envoi du lot échoué ({len(batch)} messages) — {exc}")
                    continue

                # Expo renvoie un ticket par message, dans l'ordre du lot.
                for message, ticket in zip(batch, tickets):
                    if ticket.get("status") == "ok":
                        result.delivered += 1
                        continue

                    error_code = (ticket.get("details") or {}).get("error")
                    if error_code == "DeviceNotRegistered":
                        result.invalid_tokens.append(message.token)
                    else:
                        logger.warning(
                            f"Expo push refusé pour {message.token[:24]}… — "
                            f"{error_code or ticket.get('message')}"
                        )

        return result
