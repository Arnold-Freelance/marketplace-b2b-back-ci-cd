"""
Service pour gérer les notifications système
"""
from typing import List, Optional
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.core.enums import ORDER_NOTIFICATION_TYPES
from app.repositories.notification_repo import NotificationRepository
from app.repositories.messaging_repo import ConversationRepository
from app.schemas.notification import NotificationSchema, CreateNotificationSchema, NotificationSummarySchema
from app.schemas.base import ResponseBase
from app.mappers.notification_mapper import NotificationMapper
from app.models.messaging_entity import NotificationType
from app.core.logger import logger
from app.services.push.dispatcher import PushDispatcher
from app.websocket.connection_manager import manager

#: Durée de vie d'une notification avant purge (cf. NOTIFICATIONS_V1.md §7.4).
NOTIFICATION_TTL = timedelta(days=30)

#: Exclu du badge cloche : les messages ont leur propre compteur sur l'onglet
#: Messages. Les compter aussi dans la cloche double-compterait l'évènement.
BELL_EXCLUDED_TYPES = (NotificationType.NEW_MESSAGE,)

#: Libellés par statut de commande : (type, titre, gabarit de message).
#: Les statuts absents (`pending`, `processing`, `refunded`) ne déclenchent rien —
#: soit ils sont déjà couverts par la notification de création, soit ils n'ont pas
#: de sens pour la partie adverse.
ORDER_STATUS_WORDING = {
    "confirmed": (
        NotificationType.ORDER_CONFIRMED,
        "Commande confirmée",
        "Votre commande #{order_id} a été confirmée par le fournisseur",
    ),
    "paid": (
        NotificationType.ORDER_PAID,
        "Commande payée",
        "Le paiement de la commande #{order_id} a été reçu",
    ),
    "shipped": (
        NotificationType.ORDER_SHIPPED,
        "Commande expédiée",
        "Votre commande #{order_id} a été expédiée. Numéro de suivi : {tracking_number}",
    ),
    "delivered": (
        NotificationType.ORDER_DELIVERED,
        "Commande livrée",
        "Votre commande #{order_id} a été livrée",
    ),
    "cancelled": (
        NotificationType.ORDER_CANCELLED,
        "Commande annulée",
        "La commande #{order_id} a été annulée. Motif : {reason}",
    ),
}


class NotificationService:
    """Service pour gérer les notifications"""

    def __init__(
            self,
            notification_repo: NotificationRepository,
            push_dispatcher: Optional[PushDispatcher] = None,
            conversation_repo: Optional[ConversationRepository] = None,
    ):
        self.notification_repo = notification_repo
        self.push_dispatcher = push_dispatcher
        self.conversation_repo = conversation_repo

    async def create_notification(
            self,
            user_id: int,
            notification_type: NotificationType,
            title: str,
            message: str,
            data: Optional[dict] = None,
            action_url: Optional[str] = None,
            action_label: Optional[str] = None,
            actor_id: Optional[int] = None,
            event_key: Optional[str] = None,
    ) -> Optional[NotificationSchema]:
        """
        Créer une notification, l'envoyer en temps réel, et la pousser hors-app.

        `actor_id` est l'auteur de l'action déclenchante : on ne notifie jamais
        quelqu'un de sa propre action (règle §7.1). `event_key` rend l'appel
        idempotent — un retour de retry ne crée pas de doublon (règle §7.5).

        Retourne `None` quand la notification est volontairement supprimée
        (auto-notification, ou doublon d'un `event_key` déjà émis).
        """
        try:
            if actor_id is not None and actor_id == user_id:
                logger.debug(f"Notification ignorée : user {user_id} est l'auteur de l'action")
                return None

            if event_key:
                existing = self.notification_repo.find_by_event_key(user_id, event_key)
                if existing:
                    logger.debug(f"Notification ignorée : event_key '{event_key}' déjà émis")
                    return NotificationMapper.entity_to_schema(existing)

            # Créer la notification en base
            try:
                notification = self.notification_repo.create(
                    user_id=user_id,
                    type=notification_type,
                    title=title,
                    message=message,
                    data=data or {},
                    event_key=event_key,
                    action_url=action_url,
                    action_label=action_label,
                    is_read=False,
                    expires_at=datetime.now() + NOTIFICATION_TTL,
                )
            except IntegrityError:
                # Deux workers ont franchi le `find` ensemble : la contrainte
                # d'unicité a tranché. On renvoie le gagnant, sans re-notifier.
                self.notification_repo.db.rollback()
                existing = self.notification_repo.find_by_event_key(user_id, event_key) if event_key else None
                if existing:
                    return NotificationMapper.entity_to_schema(existing)
                raise

            logger.info(f"Notification créée pour user {user_id}: {title}")

            # Convertir en schema
            notif_schema = NotificationMapper.entity_to_schema(notification)

            # Envoyer via WebSocket si l'utilisateur est connecté
            await self._send_notification_realtime(notif_schema)

            # Puis hors-app. Le dispatcher se tait de lui-même si une connexion WS
            # est vivante — sans quoi l'utilisateur recevrait deux fois l'info.
            await self._send_notification_push(notif_schema)

            return notif_schema

        except Exception as e:
            logger.error(f"Erreur create_notification: {e}")
            raise Exception(f"Erreur: {str(e)}")

    async def _send_notification_push(self, notification: NotificationSchema):
        """Pousser la notification hors-app. Un échec relais n'annule jamais le métier."""
        if not self.push_dispatcher:
            return
        try:
            await self.push_dispatcher.dispatch(notification)
        except Exception as e:
            logger.error(f"Erreur envoi push: {e}")

    async def _send_notification_realtime(self, notification: NotificationSchema):
        """Envoyer une notification en temps réel via WebSocket"""
        try:
            payload = {
                "type": "notification",
                "data": notification.model_dump()
            }

            await manager.send_personal_message(payload, notification.user_id)

        except Exception as e:
            logger.error(f"Erreur envoi notification temps réel: {e}")

    def get_my_notifications(
            self,
            user_id: int,
            unread_only: bool = False,
            limit: int = 50,
            offset: int = 0
    ) -> ResponseBase[NotificationSchema]:
        """
        Récupérer les notifications d'un utilisateur
        """
        try:
            notifications = self.notification_repo.get_user_notifications(
                user_id,
                unread_only,
                limit,
                offset
            )

            # Compter les non lues
            unread_count = self.notification_repo.count_unread(user_id)

            # Convertir
            notif_schemas = [
                NotificationMapper.entity_to_schema(notif)
                for notif in notifications
            ]

            return ResponseBase[NotificationSchema](
                success=True,
                message="Notifications récupérées",
                items=notif_schemas,
                total=len(notif_schemas),
                metadata={"unread_count": unread_count}
            )

        except Exception as e:
            logger.error(f"Erreur get_my_notifications: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def mark_as_read(self, user_id: int, notification_id: int) -> ResponseBase[NotificationSchema]:
        """Marquer une notification comme lue"""
        try:
            notification = self.notification_repo.get_by_id(notification_id)

            if not notification:
                from app.core.exceptions import NotFoundError
                raise NotFoundError("Notification non trouvée")

            if notification.user_id != user_id:
                from app.core.exceptions import BusinessRuleError
                raise BusinessRuleError("Cette notification ne vous appartient pas")

            # Marquer comme lue
            self.notification_repo.update(
                notification_id,
                is_read=True,
                read_at=datetime.now()
            )

            notif_schema = NotificationMapper.entity_to_schema(notification)

            return ResponseBase[NotificationSchema](
                success=True,
                message="Notification marquée comme lue",
                item=notif_schema
            )

        except Exception as e:
            logger.error(f"Erreur mark_as_read: {e}")
            raise

    def mark_all_as_read(
            self,
            user_id: int,
            category: Optional[str] = None,
    ) -> ResponseBase[NotificationSchema]:
        """Marquer les notifications comme lues.

        `category='orders'` ne vide que le badge Commandes ; sans catégorie, tout
        est marqué lu. Ouvrir un onglet ne doit pas éteindre les autres pastilles.
        """
        try:
            types = ORDER_NOTIFICATION_TYPES if category == "orders" else None
            count = self.notification_repo.mark_all_as_read(user_id, types=types)

            return ResponseBase[NotificationSchema](
                success=True,
                message=f"{count} notification(s) marquée(s) comme lue(s)"
            )

        except Exception as e:
            logger.error(f"Erreur mark_all_as_read: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def get_summary(
            self,
            user_id: int,
            role: Optional[str] = None,
    ) -> ResponseBase[NotificationSummarySchema]:
        """Compteurs des pastilles (cf. NOTIFICATIONS_V1.md §6).

        Source unique : le client n'a rien à recalculer ni à arbitrer entre deux
        endpoints. `messages` vient des compteurs dénormalisés de conversation,
        autoritatifs ; `orders` et `bell` des notifications non lues.
        """
        messages = (
            self.conversation_repo.get_total_unread_messages(user_id, role=role)
            if self.conversation_repo
            else 0
        )
        orders = self.notification_repo.count_unread_by_types(user_id, ORDER_NOTIFICATION_TYPES)
        bell = self.notification_repo.count_unread_excluding_types(user_id, BELL_EXCLUDED_TYPES)

        summary = NotificationSummarySchema(
            messages=messages,
            orders=orders,
            bell=bell,
            # `orders` est un sous-ensemble de `bell` : les additionner gonflerait
            # le total. Le total est « ce qui réclame une action », soit bell + messages.
            total=bell + messages,
        )

        return ResponseBase[NotificationSummarySchema](
            success=True,
            message="Compteurs récupérés",
            item=summary,
        )

    def delete_notification(self, user_id: int, notification_id: int) -> ResponseBase[NotificationSchema]:
        """Supprimer une notification appartenant à l'utilisateur."""
        from app.core.exceptions import BusinessRuleError, NotFoundError

        notification = self.notification_repo.get_by_id(notification_id, raise_if_missing=False)
        if not notification:
            raise NotFoundError("Notification", notification_id)
        if notification.user_id != user_id:
            raise BusinessRuleError("Cette notification ne vous appartient pas")

        self.notification_repo.delete(notification_id)
        return ResponseBase[NotificationSchema](
            success=True,
            message="Notification supprimée",
        )

    # ==================== MÉTHODES HELPER POUR CRÉER DES NOTIFICATIONS ====================

    async def notify_order_created(self, order_id: int, supplier_id: int, actor_id: Optional[int] = None):
        """Notifier le fournisseur d'une nouvelle commande"""
        await self.create_notification(
            user_id=supplier_id,
            notification_type=NotificationType.ORDER_CREATED,
            title="Nouvelle commande reçue",
            message=f"Vous avez reçu une nouvelle commande #{order_id}",
            data={"type": NotificationType.ORDER_CREATED.value, "order_id": order_id},
            action_url=f"/orders/{order_id}",
            action_label="Voir la commande",
            actor_id=actor_id,
            event_key=f"order:{order_id}:created",
        )

    async def notify_order_status_changed(
            self,
            order_id: int,
            new_status: str,
            buyer_id: int,
            supplier_id: int,
            actor_id: int,
            tracking_number: Optional[str] = None,
            reason: Optional[str] = None,
    ):
        """Notifier le changement de statut d'une commande.

        Le destinataire est toujours la partie *opposée* à l'auteur du changement :
        un fournisseur qui expédie prévient l'acheteur, un acheteur qui annule
        prévient le fournisseur. `create_notification` refuse déjà l'auto-notification,
        mais résoudre le destinataire ici évite d'émettre un appel pour rien.
        """
        recipient_id = buyer_id if actor_id == supplier_id else supplier_id
        wording = ORDER_STATUS_WORDING.get(new_status)
        if not wording:
            # Statut sans notification dédiée (ex. `processing`) : rien à annoncer.
            return

        notification_type, title, template = wording
        message = template.format(
            order_id=order_id,
            tracking_number=tracking_number or "—",
            reason=reason or "—",
        )

        await self.create_notification(
            user_id=recipient_id,
            notification_type=notification_type,
            title=title,
            message=message,
            data={
                "type": notification_type.value,
                "order_id": order_id,
                **({"tracking_number": tracking_number} if tracking_number else {}),
            },
            action_url=f"/orders/{order_id}",
            action_label="Voir la commande",
            actor_id=actor_id,
            # Idempotent : un retry du client ne crée pas de doublon, et repasser
            # deux fois par le même statut ne re-notifie pas.
            event_key=f"order:{order_id}:status:{new_status}",
        )

    async def notify_payment_success(self, order_id: int, buyer_id: int, amount: float):
        """Notifier l'acheteur que son paiement est réussi"""
        await self.create_notification(
            user_id=buyer_id,
            notification_type=NotificationType.PAYMENT_SUCCESS,
            title="Paiement réussi",
            message=f"Votre paiement de {amount} XOF a été validé avec succès",
            data={"type": NotificationType.PAYMENT_SUCCESS.value, "order_id": order_id, "amount": amount},
            action_url=f"/orders/{order_id}",
            action_label="Voir ma commande",
            event_key=f"order:{order_id}:payment_success",
        )

    async def notify_new_message(
            self,
            conversation_id: int,
            recipient_id: int,
            sender_name: str,
            actor_id: Optional[int] = None,
            message_id: Optional[int] = None,
    ):
        """Notifier d'un nouveau message"""
        await self.create_notification(
            user_id=recipient_id,
            notification_type=NotificationType.NEW_MESSAGE,
            title="Nouveau message",
            message=f"{sender_name} vous a envoyé un message",
            data={
                "type": NotificationType.NEW_MESSAGE.value,
                "conversation_id": conversation_id,
            },
            action_url=f"/messages/{conversation_id}",
            action_label="Lire le message",
            actor_id=actor_id,
            event_key=f"message:{message_id}" if message_id else None,
        )

    async def notify_low_stock(self, product_id: int, supplier_id: int, product_name: str, stock: int):
        """Notifier le fournisseur d'un stock faible (ou d'une rupture)."""
        out_of_stock = stock <= 0
        notification_type = (
            NotificationType.PRODUCT_OUT_STOCK if out_of_stock else NotificationType.PRODUCT_LOW_STOCK
        )
        await self.create_notification(
            user_id=supplier_id,
            notification_type=notification_type,
            title="Rupture de stock" if out_of_stock else "Stock faible",
            message=(
                f"Le produit '{product_name}' est en rupture de stock"
                if out_of_stock
                else f"Le produit '{product_name}' a un stock faible ({stock} restant)"
            ),
            data={"type": notification_type.value, "product_id": product_id, "stock": stock},
            action_url=f"/products/{product_id}/edit",
            action_label="Réapprovisionner",
            # Un seul rappel par franchissement de seuil : sans ça, chaque commande
            # sur un produit déjà bas re-notifierait le fournisseur.
            event_key=f"product:{product_id}:stock:{'out' if out_of_stock else 'low'}",
        )

    async def notify_review_received(
            self,
            product_id: int,
            supplier_id: int,
            product_name: str,
            rating: int,
            actor_id: Optional[int] = None,
            review_id: Optional[int] = None,
    ):
        """Notifier le fournisseur d'un nouvel avis sur un de ses produits."""
        await self.create_notification(
            user_id=supplier_id,
            notification_type=NotificationType.REVIEW_RECEIVED,
            title="Nouvel avis reçu",
            message=f"Votre produit '{product_name}' a reçu un avis {rating}/5",
            data={
                "type": NotificationType.REVIEW_RECEIVED.value,
                "product_id": product_id,
                "rating": rating,
            },
            action_url=f"/products/{product_id}",
            action_label="Voir l'avis",
            actor_id=actor_id,
            event_key=f"review:{review_id}" if review_id else None,
        )