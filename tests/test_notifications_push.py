"""Tests T8 — notifications push, jetons d'appareil et compteurs de pastilles.

Couvre les règles métier de NOTIFICATIONS_V1.md :
- §4.1 un jeton appartient à un seul compte (réassignation à la connexion) ;
- §6   `bell` exclut `new_message`, `total = bell + messages` ;
- §7.1 on ne notifie jamais l'auteur de l'action ;
- §7.2 pas de push si une connexion WebSocket est vivante ;
- §7.3 les messages d'un même fil partagent un `collapse_id` ;
- §7.5 `event_key` rend `create_notification` idempotent ;
- §7.6 un jeton `DeviceNotRegistered` est désactivé ;
- §7.7 `unregister` est scopé au propriétaire du jeton.

Test DB réel (SQLite en mémoire) exerçant les vrais repos et services.
"""
import asyncio
from typing import List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main_new  # noqa: F401 — charge toutes les entités
from app.core.enums import DevicePlatform, NotificationType, PushProvider, UserType
from app.db.base import Base
from app.models.messaging_entity import ConversationEntity, DeviceTokenEntity
from app.models.user_entity import UserEntity
from app.repositories.device_token_repo import DeviceTokenRepository
from app.repositories.messaging_repo import ConversationRepository
from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import RegisterDeviceSchema
from app.services.device_token_service import DeviceTokenService
from app.services.notification_service import NotificationService
from app.services.push.dispatcher import PushDispatcher
from app.services.push.provider import PushMessage, PushProviderBase, PushResult
from app.websocket.connection_manager import manager


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _clear_ws_connections():
    """Le `manager` est un singleton : on isole chaque test de ses voisins."""
    manager.active_connections.clear()
    yield
    manager.active_connections.clear()


def _user(db, email, phone, user_type=UserType.buyer) -> UserEntity:
    u = UserEntity(
        email=email, phone=phone, password_hash="x", user_type=user_type, status="active"
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


class FakeProvider(PushProviderBase):
    """Relais push en mémoire — capture ce qui aurait été envoyé."""

    def __init__(self, invalid_tokens: List[str] | None = None):
        self.sent: List[PushMessage] = []
        self.invalid_tokens = invalid_tokens or []

    async def send(self, messages: List[PushMessage]) -> PushResult:
        self.sent.extend(messages)
        delivered = len([m for m in messages if m.token not in self.invalid_tokens])
        return PushResult(delivered=delivered, invalid_tokens=list(self.invalid_tokens))


def _service(db, dispatcher=None) -> NotificationService:
    return NotificationService(
        NotificationRepository(db),
        push_dispatcher=dispatcher,
        conversation_repo=ConversationRepository(db),
    )


# ============================================================
# §4.1 — Jetons d'appareil
# ============================================================

def test_upsert_reassigne_le_jeton_au_nouveau_compte(db):
    """Un appareil qui change de compte ne doit pas produire deux lignes :
    sinon l'ancien propriétaire continuerait de recevoir les notifications."""
    alice = _user(db, "alice@x.io", "0101")
    bob = _user(db, "bob@x.io", "0202")
    repo = DeviceTokenRepository(db)

    repo.upsert(alice.id, "ExponentPushToken[aaa]", DevicePlatform.ANDROID)
    repo.upsert(bob.id, "ExponentPushToken[aaa]", DevicePlatform.ANDROID)

    assert db.query(DeviceTokenEntity).count() == 1
    assert repo.get_active_tokens(alice.id) == []
    assert len(repo.get_active_tokens(bob.id)) == 1


def test_upsert_desactive_lancien_jeton_du_meme_appareil(db):
    """Une réinstallation émet un nouveau jeton pour le même `device_id`."""
    alice = _user(db, "alice@x.io", "0101")
    repo = DeviceTokenRepository(db)

    repo.upsert(alice.id, "ExponentPushToken[old]", DevicePlatform.ANDROID, device_id="pixel-7")
    repo.upsert(alice.id, "ExponentPushToken[new]", DevicePlatform.ANDROID, device_id="pixel-7")

    actifs = repo.get_active_tokens(alice.id)
    assert [t.token for t in actifs] == ["ExponentPushToken[new]"]


def test_unregister_ne_touche_pas_le_jeton_dun_autre_compte(db):
    """§7.7 — un jeton divulgué ne doit pas permettre de couper les notifications d'autrui."""
    alice = _user(db, "alice@x.io", "0101")
    bob = _user(db, "bob@x.io", "0202")
    repo = DeviceTokenRepository(db)
    repo.upsert(alice.id, "ExponentPushToken[aaa]", DevicePlatform.IOS)

    DeviceTokenService(repo).unregister(bob.id, "ExponentPushToken[aaa]")

    assert len(repo.get_active_tokens(alice.id)) == 1, "Bob ne doit pas pouvoir désactiver le jeton d'Alice"

    DeviceTokenService(repo).unregister(alice.id, "ExponentPushToken[aaa]")
    assert repo.get_active_tokens(alice.id) == []


def test_register_via_le_service(db):
    alice = _user(db, "alice@x.io", "0101")
    service = DeviceTokenService(DeviceTokenRepository(db))

    response = service.register(
        alice.id,
        RegisterDeviceSchema(
            token="ExponentPushToken[zzz]",
            platform=DevicePlatform.ANDROID,
            provider=PushProvider.EXPO,
            device_id="pixel-8",
        ),
    )

    assert response.success is True
    assert response.item.token == "ExponentPushToken[zzz]"
    assert response.item.is_active is True


# ============================================================
# §7.1 / §7.5 — Création de notification
# ============================================================

def test_pas_dauto_notification(db):
    """§7.1 — le fournisseur qui confirme sa commande ne se notifie pas lui-même."""
    alice = _user(db, "alice@x.io", "0101")
    service = _service(db)

    result = asyncio.run(service.create_notification(
        user_id=alice.id,
        notification_type=NotificationType.ORDER_CONFIRMED,
        title="Commande confirmée",
        message="…",
        actor_id=alice.id,
    ))

    assert result is None
    assert NotificationRepository(db).count_unread(alice.id) == 0


def test_event_key_rend_la_creation_idempotente(db):
    """§7.5 — un retry sur le même évènement ne crée pas de doublon."""
    alice = _user(db, "alice@x.io", "0101")
    service = _service(db)

    async def _emit():
        return await service.create_notification(
            user_id=alice.id,
            notification_type=NotificationType.ORDER_SHIPPED,
            title="Commande expédiée",
            message="…",
            data={"order_id": 123},
            event_key="order:123:shipped",
        )

    first = asyncio.run(_emit())
    second = asyncio.run(_emit())

    assert first.id == second.id
    assert NotificationRepository(db).count_unread(alice.id) == 1


def test_event_key_resiste_a_la_course_concurrente(db):
    """§7.5 — deux workers franchissent le `find` ensemble : c'est la contrainte
    unique qui tranche, pas le check applicatif. On simule en neutralisant le
    court-circuit, ce qui force le chemin `IntegrityError`."""
    alice = _user(db, "alice@x.io", "0101")
    service = _service(db)

    async def _emit():
        return await service.create_notification(
            user_id=alice.id,
            notification_type=NotificationType.ORDER_SHIPPED,
            title="Commande expédiée", message="…",
            event_key="order:123:shipped",
        )

    first = asyncio.run(_emit())

    # Le worker concurrent n'a rien vu venir : son `find` d'entrée renvoie None.
    # Le `find` de rattrapage, lui, doit retrouver le gagnant — on ne l'aveugle
    # que sur le premier appel.
    reel = service.notification_repo.find_by_event_key
    appels = {"n": 0}

    def find_aveugle_une_fois(*args, **kwargs):
        appels["n"] += 1
        return None if appels["n"] == 1 else reel(*args, **kwargs)

    service.notification_repo.find_by_event_key = find_aveugle_une_fois
    try:
        second = asyncio.run(_emit())
    finally:
        service.notification_repo.find_by_event_key = reel

    assert appels["n"] == 2, "le rattrapage post-IntegrityError doit re-chercher le gagnant"

    assert second is not None, "le perdant de la course doit récupérer la notification gagnante"
    assert second.id == first.id
    assert NotificationRepository(db).count_unread(alice.id) == 1


def test_event_keys_distincts_creent_deux_notifications(db):
    alice = _user(db, "alice@x.io", "0101")
    service = _service(db)

    for key in ("order:1:shipped", "order:2:shipped"):
        asyncio.run(service.create_notification(
            user_id=alice.id,
            notification_type=NotificationType.ORDER_SHIPPED,
            title="Commande expédiée",
            message="…",
            event_key=key,
        ))

    assert NotificationRepository(db).count_unread(alice.id) == 2


def test_notifications_sans_event_key_ne_collisionnent_pas(db):
    """Les `event_key` NULL ne doivent pas se heurter à la contrainte unique."""
    alice = _user(db, "alice@x.io", "0101")
    service = _service(db)

    for _ in range(3):
        asyncio.run(service.create_notification(
            user_id=alice.id,
            notification_type=NotificationType.SYSTEM_ALERT,
            title="Alerte",
            message="…",
        ))

    assert NotificationRepository(db).count_unread(alice.id) == 3


# ============================================================
# §6 — Compteurs des pastilles
# ============================================================

def _notify(service, user_id, notif_type, key=None):
    asyncio.run(service.create_notification(
        user_id=user_id, notification_type=notif_type,
        title="t", message="m", event_key=key,
    ))


def test_summary_bell_exclut_les_messages(db):
    """§6 — sinon un message compte deux fois : badge Messages ET badge cloche."""
    alice = _user(db, "alice@x.io", "0101")
    service = _service(db)

    _notify(service, alice.id, NotificationType.NEW_MESSAGE, "msg:1")
    _notify(service, alice.id, NotificationType.ORDER_SHIPPED, "order:1:shipped")
    _notify(service, alice.id, NotificationType.REVIEW_RECEIVED, "review:1")

    summary = service.get_summary(alice.id).item

    assert summary.orders == 1
    assert summary.bell == 2, "order_shipped + review_received, jamais new_message"


def test_summary_messages_vient_des_conversations(db):
    """La source autoritative est le compteur dénormalisé, pas les notifications."""
    alice = _user(db, "alice@x.io", "0101")
    bob = _user(db, "bob@x.io", "0202", UserType.supplier)

    db.add(ConversationEntity(
        buyer_id=alice.id, supplier_id=bob.id,
        unread_count_buyer=3, unread_count_supplier=5, is_active=True,
    ))
    db.commit()

    service = _service(db)
    assert service.get_summary(alice.id).item.messages == 3
    assert service.get_summary(bob.id).item.messages == 5


def test_summary_messages_scope_par_role(db):
    """Un utilisateur cumulant les deux rôles : `?role=` restreint à l'espace actif."""
    hybride = _user(db, "both@x.io", "0303", UserType.supplier)
    autre = _user(db, "autre@x.io", "0404")

    db.add(ConversationEntity(
        buyer_id=hybride.id, supplier_id=autre.id,
        unread_count_buyer=4, unread_count_supplier=0, is_active=True,
    ))
    db.add(ConversationEntity(
        buyer_id=autre.id, supplier_id=hybride.id,
        unread_count_buyer=0, unread_count_supplier=7, is_active=True,
    ))
    db.commit()

    service = _service(db)
    assert service.get_summary(hybride.id).item.messages == 11
    assert service.get_summary(hybride.id, role="buyer").item.messages == 4
    assert service.get_summary(hybride.id, role="supplier").item.messages == 7


def test_summary_total_nadditionne_pas_orders_et_bell(db):
    """`orders` est un sous-ensemble de `bell` : total = bell + messages."""
    alice = _user(db, "alice@x.io", "0101")
    bob = _user(db, "bob@x.io", "0202", UserType.supplier)
    db.add(ConversationEntity(
        buyer_id=alice.id, supplier_id=bob.id,
        unread_count_buyer=2, unread_count_supplier=0, is_active=True,
    ))
    db.commit()

    service = _service(db)
    _notify(service, alice.id, NotificationType.ORDER_SHIPPED, "order:1:shipped")
    _notify(service, alice.id, NotificationType.SYSTEM_ALERT, "sys:1")

    summary = service.get_summary(alice.id).item

    assert (summary.orders, summary.bell, summary.messages) == (1, 2, 2)
    assert summary.total == 4


def test_read_all_par_categorie_ne_vide_que_les_commandes(db):
    alice = _user(db, "alice@x.io", "0101")
    service = _service(db)
    _notify(service, alice.id, NotificationType.ORDER_SHIPPED, "order:1:shipped")
    _notify(service, alice.id, NotificationType.SYSTEM_ALERT, "sys:1")

    service.mark_all_as_read(alice.id, category="orders")

    summary = service.get_summary(alice.id).item
    assert summary.orders == 0
    assert summary.bell == 1, "l'alerte système reste non lue"


# ============================================================
# §7.2 / §7.3 / §7.6 — Dispatcher push
# ============================================================

def _notification_schema(service, user_id, notif_type, data=None, key=None):
    return asyncio.run(service.create_notification(
        user_id=user_id, notification_type=notif_type,
        title="t", message="m", data=data, event_key=key,
    ))


def test_pas_de_push_si_lutilisateur_est_en_ligne(db):
    """§7.2 — l'app ouverte a déjà reçu la notification par WebSocket."""
    alice = _user(db, "alice@x.io", "0101")
    repo = DeviceTokenRepository(db)
    repo.upsert(alice.id, "ExponentPushToken[aaa]", DevicePlatform.ANDROID)

    provider = FakeProvider()
    dispatcher = PushDispatcher(repo, provider=provider)
    notif = _notification_schema(_service(db), alice.id, NotificationType.ORDER_SHIPPED, key="o:1")

    manager.active_connections[alice.id] = {object()}
    delivered = asyncio.run(dispatcher.dispatch(notif))

    assert delivered == 0
    assert provider.sent == []


def test_push_envoye_si_hors_ligne(db):
    alice = _user(db, "alice@x.io", "0101")
    repo = DeviceTokenRepository(db)
    repo.upsert(alice.id, "ExponentPushToken[aaa]", DevicePlatform.ANDROID)

    provider = FakeProvider()
    dispatcher = PushDispatcher(repo, provider=provider)
    notif = _notification_schema(_service(db), alice.id, NotificationType.ORDER_SHIPPED,
                                 data={"order_id": 7}, key="o:7")

    delivered = asyncio.run(dispatcher.dispatch(notif))

    assert delivered == 1
    assert provider.sent[0].token == "ExponentPushToken[aaa]"
    assert provider.sent[0].data["order_id"] == 7
    assert provider.sent[0].data["type"] == "order_shipped"


def test_types_silencieux_ne_reveillent_pas_le_telephone(db):
    """§5 — « il reste 4 unités » ne justifie pas une vibration."""
    alice = _user(db, "alice@x.io", "0101")
    repo = DeviceTokenRepository(db)
    repo.upsert(alice.id, "ExponentPushToken[aaa]", DevicePlatform.ANDROID)

    provider = FakeProvider()
    dispatcher = PushDispatcher(repo, provider=provider)
    notif = _notification_schema(_service(db), alice.id, NotificationType.PRODUCT_LOW_STOCK, key="p:1")

    assert asyncio.run(dispatcher.dispatch(notif)) == 0
    assert provider.sent == []


def test_messages_dun_meme_fil_partagent_un_collapse_id(db):
    """§7.3 — plusieurs messages d'une conversation = un seul push affiché."""
    alice = _user(db, "alice@x.io", "0101")
    repo = DeviceTokenRepository(db)
    repo.upsert(alice.id, "ExponentPushToken[aaa]", DevicePlatform.ANDROID)

    provider = FakeProvider()
    dispatcher = PushDispatcher(repo, provider=provider)
    notif = _notification_schema(_service(db), alice.id, NotificationType.NEW_MESSAGE,
                                 data={"conversation_id": 12}, key="m:1")

    asyncio.run(dispatcher.dispatch(notif))

    assert provider.sent[0].collapse_id == "conversation:12"


def test_notification_sans_conversation_na_pas_de_collapse_id(db):
    alice = _user(db, "alice@x.io", "0101")
    repo = DeviceTokenRepository(db)
    repo.upsert(alice.id, "ExponentPushToken[aaa]", DevicePlatform.ANDROID)

    provider = FakeProvider()
    dispatcher = PushDispatcher(repo, provider=provider)
    notif = _notification_schema(_service(db), alice.id, NotificationType.ORDER_PAID, key="o:9")

    asyncio.run(dispatcher.dispatch(notif))

    assert provider.sent[0].collapse_id is None


def test_jeton_invalide_est_desactive(db):
    """§7.6 — `DeviceNotRegistered` : on ne pousse plus dans le vide."""
    alice = _user(db, "alice@x.io", "0101")
    repo = DeviceTokenRepository(db)
    repo.upsert(alice.id, "ExponentPushToken[mort]", DevicePlatform.ANDROID)

    provider = FakeProvider(invalid_tokens=["ExponentPushToken[mort]"])
    dispatcher = PushDispatcher(repo, provider=provider)
    notif = _notification_schema(_service(db), alice.id, NotificationType.ORDER_PAID, key="o:9")

    asyncio.run(dispatcher.dispatch(notif))

    assert repo.get_active_tokens(alice.id) == []


def test_aucun_appareil_enregistre_ne_leve_pas(db):
    alice = _user(db, "alice@x.io", "0101")
    provider = FakeProvider()
    dispatcher = PushDispatcher(DeviceTokenRepository(db), provider=provider)
    notif = _notification_schema(_service(db), alice.id, NotificationType.ORDER_PAID, key="o:9")

    assert asyncio.run(dispatcher.dispatch(notif)) == 0


def test_echec_du_relais_ne_casse_pas_la_creation(db):
    """La notification est persistée et visible in-app même si le relais tombe."""
    alice = _user(db, "alice@x.io", "0101")
    repo = DeviceTokenRepository(db)
    repo.upsert(alice.id, "ExponentPushToken[aaa]", DevicePlatform.ANDROID)

    class BrokenProvider(PushProviderBase):
        async def send(self, messages):
            raise RuntimeError("Expo injoignable")

    service = _service(db, dispatcher=PushDispatcher(repo, provider=BrokenProvider()))

    notif = asyncio.run(service.create_notification(
        user_id=alice.id,
        notification_type=NotificationType.ORDER_PAID,
        title="Paiement reçu", message="…", event_key="o:9",
    ))

    assert notif is not None
    assert NotificationRepository(db).count_unread(alice.id) == 1
