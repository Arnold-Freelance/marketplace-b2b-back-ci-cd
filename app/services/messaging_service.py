# app/services/messaging_service.py
"""
Service pour gérer la messagerie en temps réel
"""
from typing import List, Optional
from datetime import datetime

from app.repositories.messaging_repo import ConversationRepository, MessageRepository, UserPresenceRepository
from app.repositories.user_repo import UserRepository
from app.schemas.messaging import (
    ConversationSchema, MessageSchema, CreateMessageSchema,
    ConversationCreateSchema
)
from app.schemas.base import ResponseBase
from app.mappers.messaging_mapper import ConversationMapper, MessageMapper
from app.core.exceptions import ValidationError, NotFoundError, BusinessRuleError
from app.core.logger import logger
from app.websocket.connection_manager import manager
from app.models.messaging_entity import MessageStatus
from app.services.notification_service import NotificationService


class MessagingService:
    """Service pour gérer la messagerie"""

    def __init__(
            self,
            conversation_repo: ConversationRepository,
            message_repo: MessageRepository,
            user_repo: UserRepository,
            presence_repo: UserPresenceRepository,
            notification_service: Optional[NotificationService] = None,
    ):
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.user_repo = user_repo
        self.presence_repo = presence_repo
        self.notification_service = notification_service

    def get_or_create_conversation(
            self,
            user_id: int,
            data: ConversationCreateSchema
    ) -> ResponseBase[ConversationSchema]:
        """
        Récupérer ou créer une conversation entre deux utilisateurs
        """
        try:
            # Déterminer qui est l'acheteur et qui est le fournisseur
            current_user = self.user_repo.get_by_id(user_id)
            other_user = self.user_repo.get_by_id(data.other_user_id)

            if not other_user:
                raise NotFoundError("Utilisateur non trouvé")

            # Chercher une conversation existante (scopée au même contexte :
            # une demande par produit/commande = un fil distinct).
            conversation = self.conversation_repo.get_conversation_between_users(
                user_id,
                data.other_user_id,
                data.order_id,
                data.product_id
            )

            if conversation:
                logger.info(f"Conversation existante trouvée: {conversation.id}")
            else:
                # Créer une nouvelle conversation
                # Simplification: on considère que celui qui initie est l'acheteur
                conversation = self.conversation_repo.create(
                    buyer_id=user_id,
                    supplier_id=data.other_user_id,
                    order_id=data.order_id,
                    product_id=data.product_id,
                    subject=data.subject,
                    is_active=True
                )
                logger.info(f"Nouvelle conversation créée: {conversation.id}")

            # Convertir en schema
            conv_schema = ConversationMapper.entity_to_schema(conversation)
            conv_schema = self._enrich_conversation(conv_schema, user_id)

            return ResponseBase[ConversationSchema](
                success=True,
                message="Conversation récupérée",
                item=conv_schema
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur get_or_create_conversation: {e}")
            raise Exception(f"Erreur: {str(e)}")

    async def send_message(
            self,
            user_id: int,
            data: CreateMessageSchema
    ) -> ResponseBase[MessageSchema]:
        """
        Envoyer un message dans une conversation
        """
        try:
            # Vérifier que la conversation existe
            conversation = self.conversation_repo.get_by_id(data.conversation_id)
            if not conversation:
                raise NotFoundError("Conversation non trouvée")

            # Vérifier que l'utilisateur fait partie de la conversation
            if user_id not in [conversation.buyer_id, conversation.supplier_id]:
                raise BusinessRuleError("Vous ne faites pas partie de cette conversation")

            # Créer le message
            message = self.message_repo.create(
                conversation_id=data.conversation_id,
                sender_id=user_id,
                content=data.content,
                attachments=data.attachments,
                reply_to_message_id=data.reply_to_message_id,
                status=MessageStatus.SENT,
                is_system_message=False
            )

            # Mettre à jour la conversation
            self.conversation_repo.update(
                conversation.id,
                last_message_at=datetime.now(),
                last_message_preview=data.content[:200]
            )

            # Incrémenter le compteur non lu pour le destinataire
            if user_id == conversation.buyer_id:
                self.conversation_repo.update(
                    conversation.id,
                    unread_count_supplier=conversation.unread_count_supplier + 1
                )
                recipient_id = conversation.supplier_id
            else:
                self.conversation_repo.update(
                    conversation.id,
                    unread_count_buyer=conversation.unread_count_buyer + 1
                )
                recipient_id = conversation.buyer_id

            # Convertir en schema
            message_schema = MessageMapper.entity_to_schema(message)
            message_schema = self._enrich_message(message_schema)

            logger.info(f"Message {message.id} créé dans conversation {conversation.id}")

            # Envoyer via WebSocket au destinataire
            await self._broadcast_message(message_schema, recipient_id)

            # Puis notifier : le PushDispatcher se tait de lui-même si le
            # destinataire a une connexion WebSocket vivante — il vient de
            # recevoir le message à l'écran, le pousser en double serait du bruit.
            await self._notify_new_message(conversation, message, user_id, recipient_id)

            return ResponseBase[MessageSchema](
                success=True,
                message="Message envoyé",
                item=message_schema
            )

        except (NotFoundError, BusinessRuleError, ValidationError):
            raise
        except Exception as e:
            logger.error(f"Erreur send_message: {e}")
            raise Exception(f"Erreur: {str(e)}")

    async def _broadcast_message(self, message: MessageSchema, recipient_id: int):
        """Diffuser un message via WebSocket"""
        try:
            payload = {
                "type": "new_message",
                "data": message.model_dump()
            }

            # Envoyer au destinataire
            await manager.send_personal_message(payload, recipient_id)

            # Marquer comme délivré si l'utilisateur est en ligne
            if manager.is_user_online(recipient_id):
                self.message_repo.update(
                    message.id,
                    status=MessageStatus.DELIVERED
                )

        except Exception as e:
            logger.error(f"Erreur broadcast message: {e}")

    def get_my_conversations(self, user_id: int) -> ResponseBase[ConversationSchema]:
        """
        Récupérer toutes les conversations d'un utilisateur
        """
        try:
            conversations = self.conversation_repo.get_user_conversations(user_id)

            # Convertir et enrichir
            conv_schemas = [
                ConversationMapper.entity_to_schema(conv)
                for conv in conversations
            ]
            conv_schemas = [
                self._enrich_conversation(conv, user_id)
                for conv in conv_schemas
            ]

            # Trier par dernière activité
            conv_schemas.sort(
                key=lambda x: x.last_message_at or x.created_at,
                reverse=True
            )

            return ResponseBase[ConversationSchema](
                success=True,
                message="Conversations récupérées",
                items=conv_schemas,
                total=len(conv_schemas)
            )

        except Exception as e:
            logger.error(f"Erreur get_my_conversations: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def get_conversation(
            self,
            user_id: int,
            conversation_id: int
    ) -> ResponseBase[ConversationSchema]:
        """Récupérer une conversation (réservée à ses participants)."""
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise NotFoundError("Conversation non trouvée")
        if user_id not in [conversation.buyer_id, conversation.supplier_id]:
            raise BusinessRuleError("Vous ne faites pas partie de cette conversation")

        schema = ConversationMapper.entity_to_schema(conversation)
        schema = self._enrich_conversation(schema, user_id)
        return ResponseBase[ConversationSchema](
            success=True,
            message="Conversation récupérée",
            item=schema,
        )

    def get_conversation_messages(
            self,
            user_id: int,
            conversation_id: int,
            limit: int = 50,
            offset: int = 0
    ) -> ResponseBase[MessageSchema]:
        """
        Récupérer les messages d'une conversation
        """
        try:
            # Vérifier que l'utilisateur fait partie de la conversation
            conversation = self.conversation_repo.get_by_id(conversation_id)
            if not conversation:
                raise NotFoundError("Conversation non trouvée")

            if user_id not in [conversation.buyer_id, conversation.supplier_id]:
                raise BusinessRuleError("Vous ne faites pas partie de cette conversation")

            # Récupérer les messages
            messages = self.message_repo.get_by_conversation(
                conversation_id,
                limit,
                offset
            )

            # Marquer les messages non lus comme lus
            unread_messages = [
                msg for msg in messages
                if msg.sender_id != user_id and not msg.is_read
            ]

            for msg in unread_messages:
                self.message_repo.update(
                    msg.id,
                    is_read=True,
                    read_at=datetime.now(),
                    status=MessageStatus.READ
                )

            # Réinitialiser le compteur non lu
            if user_id == conversation.buyer_id:
                self.conversation_repo.update(conversation_id, unread_count_buyer=0)
            else:
                self.conversation_repo.update(conversation_id, unread_count_supplier=0)

            # Convertir et enrichir
            message_schemas = [
                MessageMapper.entity_to_schema(msg)
                for msg in messages
            ]
            message_schemas = [
                self._enrich_message(msg)
                for msg in message_schemas
            ]

            return ResponseBase[MessageSchema](
                success=True,
                message="Messages récupérés",
                items=message_schemas,
                total=len(message_schemas)
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur get_conversation_messages: {e}")
            raise Exception(f"Erreur: {str(e)}")

    async def mark_as_read(
            self,
            user_id: int,
            message_id: int
    ) -> ResponseBase[MessageSchema]:
        """
        Marquer un message comme lu
        """
        try:
            message = self.message_repo.get_by_id(message_id)
            if not message:
                raise NotFoundError("Message non trouvé")

            # Vérifier que l'utilisateur est le destinataire
            conversation = self.conversation_repo.get_by_id(message.conversation_id)
            if message.sender_id == user_id:
                raise BusinessRuleError("Vous ne pouvez pas marquer votre propre message comme lu")

            # Marquer comme lu
            self.message_repo.update(
                message_id,
                is_read=True,
                read_at=datetime.now(),
                status=MessageStatus.READ
            )

            # Notifier l'expéditeur via WebSocket
            await manager.send_personal_message(
                {
                    "type": "message_read",
                    "data": {
                        "message_id": message_id,
                        "read_at": datetime.now().isoformat()
                    }
                },
                message.sender_id
            )

            message_schema = MessageMapper.entity_to_schema(message)

            return ResponseBase[MessageSchema](
                success=True,
                message="Message marqué comme lu",
                item=message_schema
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur mark_as_read: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def _enrich_conversation(
            self,
            conv: ConversationSchema,
            current_user_id: int
    ) -> ConversationSchema:
        """Enrichir une conversation avec les informations des participants"""
        # Informations de l'autre participant
        other_user_id = conv.supplier_id if current_user_id == conv.buyer_id else conv.buyer_id
        other_user = self.user_repo.get_by_id(other_user_id)

        if other_user:
            conv.other_user_name = self._user_display_name(other_user)
            conv.other_user_avatar = other_user.avatar_url if hasattr(other_user, 'avatar_url') else None

            # Vérifier si l'autre utilisateur est en ligne
            conv.other_user_is_online = manager.is_user_online(other_user_id)

        # Nombre de messages non lus pour l'utilisateur actuel
        conv.unread_count = (
            conv.unread_count_buyer
            if current_user_id == conv.buyer_id
            else conv.unread_count_supplier
        )

        return conv

    async def _notify_new_message(self, conversation, message, sender_id: int, recipient_id: int) -> None:
        """Créer la notification « nouveau message ». Best-effort : un relais push
        injoignable ne doit jamais faire échouer l'envoi du message lui-même."""
        if not self.notification_service:
            return
        try:
            sender = self.user_repo.get_by_id(sender_id)
            await self.notification_service.notify_new_message(
                conversation_id=conversation.id,
                recipient_id=recipient_id,
                sender_name=self._user_display_name(sender) if sender else "Un utilisateur",
                actor_id=sender_id,
                message_id=message.id,
            )
        except Exception as e:
            logger.error(f"Notification 'nouveau message' non émise (message envoyé): {e}")

    @staticmethod
    def _user_display_name(user) -> str:
        """Nom affichable depuis le profil entreprise (UserEntity n'a pas de
        first_name/last_name). Fallback sur l'email."""
        profile = getattr(user, "company_profile", None)
        if profile and (profile.company_name or profile.contact_person):
            return profile.company_name or profile.contact_person
        return getattr(user, "email", "") or "Utilisateur"

    def _enrich_message(self, message: MessageSchema) -> MessageSchema:
        """Enrichir un message avec les informations de l'expéditeur"""
        sender = self.user_repo.get_by_id(message.sender_id)
        if sender:
            message.sender_name = self._user_display_name(sender)
            message.sender_avatar = sender.avatar_url if hasattr(sender, 'avatar_url') else None

        return message