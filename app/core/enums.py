# ================================================
# ENUMS
# ================================================
from enum import Enum

class UserType(str, Enum):
    """Types d'utilisateurs"""
    supplier = "supplier"
    buyer = "buyer"
    admin = "admin"


class UserStatus(str, Enum):
    """Statuts d'utilisateurs"""
    pending = "pending"
    active = "active"
    suspended = "suspended"
    inactive = "inactive"

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class PaymentMethod(str, Enum):
    WAVE = "wave"
    CINETPAY = "cinetpay"
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"


# Messaging Status
class MessageStatus(str, Enum):
    """Statuts d'un message"""
    SENT = "sent"  # Envoyé
    DELIVERED = "delivered"  # Délivré (reçu par le serveur)
    READ = "read"  # Lu par le destinataire
    FAILED = "failed"  # Échec d'envoi


class NotificationType(str, Enum):
    """Types de notifications"""
    ORDER_CREATED = "order_created"  # Nouvelle commande
    ORDER_CONFIRMED = "order_confirmed"  # Commande confirmée
    ORDER_PAID = "order_paid"  # Commande payée
    ORDER_SHIPPED = "order_shipped"  # Commande expédiée
    ORDER_DELIVERED = "order_delivered"  # Commande livrée
    ORDER_CANCELLED = "order_cancelled"  # Commande annulée
    PAYMENT_SUCCESS = "payment_success"  # Paiement réussi
    PAYMENT_FAILED = "payment_failed"  # Paiement échoué
    NEW_MESSAGE = "new_message"  # Nouveau message
    PRODUCT_LOW_STOCK = "product_low_stock"  # Stock faible
    PRODUCT_OUT_STOCK = "product_out_of_stock"  # Rupture de stock
    REVIEW_RECEIVED = "review_received"  # Nouvel avis reçu
    SYSTEM_ALERT = "system_alert"  # Alerte système


class PushProvider(str, Enum):
    """Relais d'envoi des notifications push.

    `expo` est le seul implémenté (cf. NOTIFICATIONS_V1.md §3). `fcm` existe pour
    permettre une bascule vers FCM direct sans migration des tokens existants.
    """
    EXPO = "expo"
    FCM = "fcm"


class DevicePlatform(str, Enum):
    """Plateforme de l'appareil enregistré."""
    ANDROID = "android"
    IOS = "ios"


#: Notifications qui alimentent le badge de l'onglet « Commandes » (cf. specs §6).
ORDER_NOTIFICATION_TYPES = (
    NotificationType.ORDER_CREATED,
    NotificationType.ORDER_CONFIRMED,
    NotificationType.ORDER_PAID,
    NotificationType.ORDER_SHIPPED,
    NotificationType.ORDER_DELIVERED,
    NotificationType.ORDER_CANCELLED,
    NotificationType.PAYMENT_SUCCESS,
    NotificationType.PAYMENT_FAILED,
)