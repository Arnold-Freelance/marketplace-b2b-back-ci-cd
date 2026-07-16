"""
Service d'enregistrement des appareils pour les notifications push.
"""
from app.core.logger import logger
from app.mappers.device_token_mapper import DeviceTokenMapper
from app.repositories.device_token_repo import DeviceTokenRepository
from app.schemas.base import ResponseBase
from app.schemas.notification import DeviceTokenSchema, RegisterDeviceSchema


class DeviceTokenService:
    """Enregistre / désenregistre les jetons push."""

    def __init__(self, device_repo: DeviceTokenRepository):
        self.device_repo = device_repo

    def register(self, user_id: int, data: RegisterDeviceSchema) -> ResponseBase[DeviceTokenSchema]:
        """Enregistre le jeton de l'appareil courant pour l'utilisateur connecté."""
        device = self.device_repo.upsert(
            user_id=user_id,
            token=data.token,
            platform=data.platform,
            provider=data.provider,
            device_id=data.device_id,
        )
        logger.info(f"Jeton push enregistré pour user {user_id} ({data.platform.value})")

        return ResponseBase[DeviceTokenSchema](
            success=True,
            message="Appareil enregistré",
            item=DeviceTokenMapper.entity_to_schema(device),
        )

    def unregister(self, user_id: int, token: str) -> ResponseBase[DeviceTokenSchema]:
        """Désactive un jeton. Appelé au logout.

        Sans cet appel, le prochain utilisateur de l'appareil recevrait les
        notifications du précédent — fuite de données (règle §7.7).

        L'action est scopée au propriétaire du jeton : au login, `upsert` a réassigné
        le jeton de cet appareil à l'utilisateur courant, donc il lui appartient bien.
        Reste idempotent si le jeton est déjà inactif ou inconnu.
        """
        self.device_repo.deactivate(token, user_id=user_id)

        return ResponseBase[DeviceTokenSchema](
            success=True,
            message="Appareil désenregistré",
        )
