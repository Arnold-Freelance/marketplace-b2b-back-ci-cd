# app/services/order_service.py
"""
Service pour gérer les commandes
"""
from typing import List, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import uuid

from app.repositories.address_repo import AddressRepository
from app.repositories.order_repo import OrderRepository, OrderItemRepository, OrderStatusHistoryRepository
from app.repositories.cart_repo import CartRepository, CartItemRepository
from app.repositories.company_profile_repo import CompanyProfileRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.payment_repo import PaymentRepository
from app.models.order_entity import OrderStatus, PaymentStatus, ShippingMethod
from app.schemas.address import AddressSchema
from app.schemas.order import (
    OrderSchema, CreateOrderSchema, UpdateOrderStatusSchema,
    CancelOrderSchema, ShippingAddressSchema,
    QuoteSchema, QuoteSupplierSchema, QuoteItemSchema,
)
from app.schemas.base import ResponseBase
from app.mappers.order_mapper import OrderMapper
from app.core.exceptions import ValidationError, NotFoundError, BusinessRuleError
from app.core.logger import logger
from app.services.notification_service import NotificationService

#: Seuil sous lequel on prévient le fournisseur qu'il doit réapprovisionner.
LOW_STOCK_THRESHOLD = 5


class OrderService:
    """Service pour gérer les commandes"""

    def __init__(
            self,
            order_repo: OrderRepository,
            order_item_repo: OrderItemRepository,
            order_history_repo: OrderStatusHistoryRepository,
            cart_repo: CartRepository,
            cart_item_repo: CartItemRepository,
            product_repo: ProductRepository,
            payment_repo: PaymentRepository,
            notification_service: Optional[NotificationService] = None,
            company_profile_repo: Optional[CompanyProfileRepository] = None,
            address_repo: Optional[AddressRepository] = None,
    ):
        self.order_repo = order_repo
        self.order_item_repo = order_item_repo
        self.order_history_repo = order_history_repo
        self.cart_repo = cart_repo
        self.cart_item_repo = cart_item_repo
        self.product_repo = product_repo
        self.payment_repo = payment_repo
        self.notification_service = notification_service
        # Porte le barème de livraison du fournisseur (cf. compute_shipping_cost).
        self.company_profile_repo = company_profile_repo
        # Résout `address_id` -> adresse de livraison (cf. _resolve_shipping_address).
        self.address_repo = address_repo

    async def _notify(self, coro_factory) -> None:
        """Émettre une notification sans jamais faire échouer le métier.

        Une commande créée reste créée même si le relais push est injoignable ou
        si le service de notification n'est pas injecté (tests, scripts).
        """
        if not self.notification_service:
            return
        try:
            await coro_factory(self.notification_service)
        except Exception as e:
            logger.error(f"Notification non émise (métier inchangé): {e}")

    async def create_order_from_cart(
            self,
            user_id: int,
            data: CreateOrderSchema
    ) -> ResponseBase[OrderSchema]:
        """
        Créer une commande à partir du panier actif
        """
        try:
            # Récupérer le panier actif
            cart = self.cart_repo.get_active_cart(user_id)
            if not cart or not cart.cart_items:
                raise BusinessRuleError("Votre panier est vide")

            # Résoudre l'adresse du carnet AVANT de créer quoi que ce soit :
            # une adresse invalide doit échouer sans avoir touché au stock.
            data.shipping_address = self._resolve_shipping_address(user_id, data)

            # Grouper les items par fournisseur (une commande par fournisseur)
            orders_by_supplier = {}

            for cart_item in cart.cart_items:
                product = self.product_repo.get_by_id(cart_item.product_id)

                # Validations
                if not product:
                    raise NotFoundError(f"Produit {cart_item.product_id} non trouvé")

                if not product.is_active:
                    raise BusinessRuleError(f"Le produit '{product.name}' n'est plus disponible")

                if product.stock_quantity < cart_item.quantity:
                    raise BusinessRuleError(
                        f"Stock insuffisant pour '{product.name}'. "
                        f"Disponible: {product.stock_quantity}"
                    )

                # Grouper par fournisseur
                supplier_id = product.supplier_id
                if supplier_id not in orders_by_supplier:
                    orders_by_supplier[supplier_id] = []

                orders_by_supplier[supplier_id].append({
                    'cart_item': cart_item,
                    'product': product
                })

            # Créer une commande pour chaque fournisseur
            created_orders = []
            stock_alerts: List[dict] = []

            for supplier_id, items in orders_by_supplier.items():
                order = self._create_single_order(
                    buyer_id=user_id,
                    supplier_id=supplier_id,
                    items=items,
                    shipping_data=data,
                    stock_alerts=stock_alerts,
                )
                created_orders.append(order)

            # Vider le panier après création des commandes
            self.cart_item_repo.delete_by_cart_id(cart.id)

            logger.info(f"{len(created_orders)} commande(s) créée(s) pour utilisateur {user_id}")

            # Notifier une fois le métier bouclé : le fournisseur d'abord (nouvelle
            # commande), puis les alertes de stock que la déduction vient de faire
            # franchir. Émis ici, et pas dans `_create_single_order`, pour qu'un
            # relais push lent ne retienne pas la transaction.
            for order in created_orders:
                await self._notify(
                    lambda svc, o=order: svc.notify_order_created(
                        order_id=o.id,
                        supplier_id=o.supplier_id,
                        actor_id=user_id,
                    )
                )

            for alert in stock_alerts:
                await self._notify(
                    lambda svc, a=alert: svc.notify_low_stock(
                        product_id=a["product_id"],
                        supplier_id=a["supplier_id"],
                        product_name=a["product_name"],
                        stock=a["stock"],
                    )
                )

            # Retourner les commandes créées
            orders_schema = [OrderMapper.entity_to_schema(order) for order in created_orders]
            orders_schema = [self._enrich_order(o) for o in orders_schema]

            return ResponseBase[OrderSchema](
                success=True,
                message=f"{len(created_orders)} commande(s) créée(s) avec succès",
                items=orders_schema
            )

        except (ValidationError, NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur création commande: {e}")
            raise Exception(f"Erreur lors de la création de la commande: {str(e)}")

    def _create_single_order(
            self,
            buyer_id: int,
            supplier_id: int,
            items: List[dict],
            shipping_data: CreateOrderSchema,
            stock_alerts: Optional[List[dict]] = None,
    ):
        """
        Créer une commande unique pour un fournisseur

        `stock_alerts` est rempli au fil de la déduction de stock : l'appelant y
        trouve les produits passés sous le seuil, et les notifie une fois la
        transaction close.
        """
        # Calculer les montants
        subtotal = Decimal("0.00")

        for item_data in items:
            product = item_data['product']
            cart_item = item_data['cart_item']
            subtotal += product.price * cart_item.quantity

        shipping_cost = self.compute_shipping_cost(
            supplier_id=supplier_id,
            products=[i['product'] for i in items],
            subtotal=subtotal,
            shipping_method=shipping_data.shipping_method,
        )

        # Les prix produits sont TTC : pas de taxe ajoutée au-dessus. La colonne
        # `tax_amount` est conservée pour une facturation détaillée ultérieure.
        tax_amount = Decimal("0")

        total_amount = subtotal + shipping_cost + tax_amount

        # Générer un numéro de commande unique
        order_number = self._generate_order_number()

        # Date de livraison estimée
        delivery_days = {
            ShippingMethod.SAME_DAY: 0,
            ShippingMethod.EXPRESS: 2,
            ShippingMethod.STANDARD: 7,
            ShippingMethod.PICKUP: 1,
        }
        estimated_delivery = datetime.now() + timedelta(
            days=delivery_days.get(shipping_data.shipping_method, 7)
        )

        # Créer la commande
        order = self.order_repo.create(
            order_number=order_number,
            buyer_id=buyer_id,
            supplier_id=supplier_id,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            tax_amount=tax_amount,
            discount_amount=Decimal("0"),
            total_amount=total_amount,
            currency="XOF",
            status=OrderStatus.PENDING,
            payment_status=PaymentStatus.PENDING,
            shipping_method=shipping_data.shipping_method,
            shipping_address=shipping_data.shipping_address.model_dump(),
            buyer_notes=shipping_data.buyer_notes,
            estimated_delivery_date=estimated_delivery,
            is_deleted=False
        )

        # Créer les items de commande
        for item_data in items:
            product = item_data['product']
            cart_item = item_data['cart_item']

            # Image principale
            primary_image_url = None
            if product.product_images:
                primary_image = next(
                    (img for img in product.product_images if img.is_primary and not img.is_deleted),
                    None
                )
                if primary_image:
                    primary_image_url = primary_image.thumbnail_url
                elif product.product_images:
                    primary_image_url = product.product_images[0].thumbnail_url

            self.order_item_repo.create(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                product_sku=product.sku,
                product_image_url=primary_image_url,
                quantity=cart_item.quantity,
                unit_price=product.price,
                subtotal=product.price * cart_item.quantity,
                currency="XOF",
                product_attributes=product.attributes
            )

            # Déduire du stock
            new_stock = product.stock_quantity - cart_item.quantity
            self.product_repo.update(product.id, stock_quantity=new_stock)

            # Seul le FRANCHISSEMENT du seuil alerte : un produit déjà sous le
            # seuil avant la commande a déjà fait l'objet d'une notification.
            if stock_alerts is not None and new_stock <= LOW_STOCK_THRESHOLD < product.stock_quantity:
                stock_alerts.append({
                    "product_id": product.id,
                    "supplier_id": supplier_id,
                    "product_name": product.name,
                    "stock": new_stock,
                })

        # Trace du moyen de paiement choisi. Sans elle, le fournisseur ne sait
        # pas s'il sera payé à la livraison ou par mobile money, ni sur quel
        # numéro : le choix de l'acheteur était jusqu'ici accepté puis jeté.
        # Statut PENDING — aucun encaissement réel n'a lieu (pas de PSP branché).
        self.payment_repo.create(
            order_id=order.id,
            payment_method=shipping_data.payment_method,
            payment_status=PaymentStatus.PENDING,
            amount=total_amount,
            currency="XOF",
            payment_provider=shipping_data.payment_provider,
            payment_details=(
                {"phone": shipping_data.payment_phone}
                if shipping_data.payment_phone else None
            ),
        )

        # Créer l'historique de statut
        self.order_history_repo.create(
            order_id=order.id,
            old_status=None,
            new_status=OrderStatus.PENDING,
            comment="Commande créée",
            changed_by=buyer_id
        )

        return order

    def quote_cart(
            self,
            user_id: int,
            shipping_method: ShippingMethod = ShippingMethod.STANDARD,
    ) -> ResponseBase[QuoteSchema]:
        """Chiffrer le panier SANS rien créer.

        Même regroupement par fournisseur et même `compute_shipping_cost` que
        `create_order_from_cart` : c'est ce qui garantit que le montant affiché
        au paiement est celui qui sera facturé. Toute règle de prix ajoutée plus
        tard doit passer par ces deux appels, jamais être recopiée côté client.
        """
        cart = self.cart_repo.get_active_cart(user_id)
        if not cart or not cart.cart_items:
            raise BusinessRuleError("Votre panier est vide")

        by_supplier: dict = {}
        for cart_item in cart.cart_items:
            product = self.product_repo.get_by_id(cart_item.product_id)
            if not product:
                raise NotFoundError(f"Produit {cart_item.product_id} non trouvé")
            if not product.is_active:
                raise BusinessRuleError(f"Le produit '{product.name}' n'est plus disponible")
            if product.stock_quantity < cart_item.quantity:
                raise BusinessRuleError(
                    f"Stock insuffisant pour '{product.name}'. Disponible: {product.stock_quantity}"
                )
            by_supplier.setdefault(product.supplier_id, []).append((cart_item, product))

        quotes: List[QuoteSupplierSchema] = []
        for supplier_id, pairs in by_supplier.items():
            items = [
                QuoteItemSchema(
                    product_id=product.id,
                    product_name=product.name,
                    product_image_url=self._primary_image_url(product),
                    quantity=cart_item.quantity,
                    unit_price=product.price,
                    subtotal=product.price * cart_item.quantity,
                )
                for cart_item, product in pairs
            ]
            subtotal = sum((i.subtotal for i in items), Decimal("0.00"))
            products = [product for _, product in pairs]

            shipping_cost = self.compute_shipping_cost(
                supplier_id=supplier_id,
                products=products,
                subtotal=subtotal,
                shipping_method=shipping_method,
            )

            profile = (
                self.company_profile_repo.get_by_user_id(supplier_id)
                if self.company_profile_repo else None
            )
            threshold = getattr(profile, "free_shipping_threshold", None) if profile else None
            threshold = Decimal(str(threshold)) if threshold is not None else None

            quotes.append(QuoteSupplierSchema(
                supplier_id=supplier_id,
                supplier_name=getattr(profile, "company_name", None) if profile else None,
                items=items,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total=subtotal + shipping_cost,
                free_shipping_applied=bool(threshold is not None and subtotal >= threshold),
                # « Encore X pour la livraison offerte » : nul dès que le franco
                # est atteint, ou qu'il n'y en a pas.
                free_shipping_remaining=(
                    threshold - subtotal
                    if threshold is not None and subtotal < threshold
                    else None
                ),
            ))

        subtotal_all = sum((q.subtotal for q in quotes), Decimal("0.00"))
        shipping_all = sum((q.shipping_cost for q in quotes), Decimal("0.00"))

        return ResponseBase[QuoteSchema](
            success=True,
            message="Devis calculé",
            item=QuoteSchema(
                orders=quotes,
                subtotal=subtotal_all,
                shipping_total=shipping_all,
                total=subtotal_all + shipping_all,
                orders_count=len(quotes),
            ),
        )

    def _resolve_shipping_address(self, user_id: int, data: CreateOrderSchema) -> ShippingAddressSchema:
        """Adresse effective de la commande.

        `address_id` l'emporte sur `shipping_address` : si le client envoie les
        deux, c'est le carnet qui fait foi — lui seul est vérifié comme
        appartenant à l'acheteur. Le repo filtre déjà sur `user_id`, donc une
        adresse d'autrui est introuvable, pas « trouvée puis refusée ».
        """
        if data.address_id is None:
            return data.shipping_address

        if not self.address_repo:
            raise BusinessRuleError("Carnet d'adresses indisponible")

        address = self.address_repo.get_owned(data.address_id, user_id)
        if not address:
            raise NotFoundError("Adresse", data.address_id)

        # Recopiée dans la commande : modifier l'adresse du carnet plus tard ne
        # doit pas réécrire l'adresse d'une commande déjà passée.
        return AddressSchema.model_validate(address).to_shipping_address()

    @staticmethod
    def _primary_image_url(product) -> Optional[str]:
        """URL de l'image principale, ou la première à défaut."""
        images = [img for img in (product.product_images or []) if not img.is_deleted]
        if not images:
            return None
        primary = next((img for img in images if img.is_primary), images[0])
        return primary.thumbnail_url or primary.image_url

    def compute_shipping_cost(
            self,
            supplier_id: int,
            products: List,
            subtotal: Decimal,
            shipping_method: ShippingMethod = ShippingMethod.STANDARD,
    ) -> Decimal:
        """Frais de livraison d'une commande, pour UN fournisseur.

        Règle (décidée avec le métier) :
          1. retrait sur place            -> 0
          2. franco de port atteint       -> 0
          3. un produit hors norme        -> la plus élevée des surcharges
          4. sinon                        -> barème de base du fournisseur

        On prend le `max` des surcharges et non leur somme : les articles d'une
        même commande partent dans le même envoi, c'est le plus encombrant qui
        dicte le coût. Les additionner ferait exploser la facture d'un gros panier.

        Sans profil entreprise (fournisseur qui n'a pas rempli son barème), on
        retombe sur 0 : mieux vaut ne rien facturer que facturer au hasard.
        """
        if shipping_method == ShippingMethod.PICKUP:
            return Decimal("0")

        profile = self.company_profile_repo.get_by_user_id(supplier_id) if self.company_profile_repo else None

        threshold = getattr(profile, "free_shipping_threshold", None) if profile else None
        if threshold is not None and subtotal >= Decimal(str(threshold)):
            return Decimal("0")

        overrides = [
            Decimal(str(p.shipping_cost_override))
            for p in products
            if getattr(p, "shipping_cost_override", None) is not None
        ]
        if overrides:
            return max(overrides)

        base = getattr(profile, "shipping_base_cost", None) if profile else None
        return Decimal(str(base)) if base is not None else Decimal("0")

    def _generate_order_number(self) -> str:
        """Générer un numéro de commande unique"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"ORD-{timestamp}-{unique_id}"

    def get_order_by_id(self, order_id: int, user_id: int) -> ResponseBase[OrderSchema]:
        """
        Récupérer une commande par ID
        """
        try:
            order = self.order_repo.get_by_id(order_id)
            if not order:
                raise NotFoundError("Commande non trouvée")

            # Vérifier que l'utilisateur est autorisé à voir cette commande
            if order.buyer_id != user_id and order.supplier_id != user_id:
                raise BusinessRuleError("Vous n'êtes pas autorisé à voir cette commande")

            order_schema = OrderMapper.entity_to_schema(order)
            order_schema = self._enrich_order(order_schema)

            return ResponseBase[OrderSchema](
                success=True,
                message="Commande récupérée avec succès",
                item=order_schema
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur récupération commande: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def get_my_orders(self, user_id: int, as_buyer: bool = True) -> ResponseBase[OrderSchema]:
        """
        Récupérer toutes les commandes d'un utilisateur
        """
        try:
            if as_buyer:
                orders = self.order_repo.get_by_buyer_id(user_id)
            else:
                orders = self.order_repo.get_by_supplier_id(user_id)

            orders_schema = [OrderMapper.entity_to_schema(order) for order in orders]
            orders_schema = [self._enrich_order(o) for o in orders_schema]

            message = "Mes commandes" if as_buyer else "Commandes reçues"

            return ResponseBase[OrderSchema](
                success=True,
                message=message,
                items=orders_schema,
                total=len(orders_schema)
            )

        except Exception as e:
            logger.error(f"Erreur récupération commandes: {e}")
            raise Exception(f"Erreur: {str(e)}")

    async def update_order_status(
            self,
            user_id: int,
            data: UpdateOrderStatusSchema
    ) -> ResponseBase[OrderSchema]:
        """
        Mettre à jour le statut d'une commande
        """
        try:
            order = self.order_repo.get_by_id(data.order_id)
            if not order:
                raise NotFoundError("Commande non trouvée")

            # Capturés avant l'update : après `order_repo.update`, l'entité est
            # rechargée et on perdrait le contexte de l'auteur du changement.
            buyer_id, supplier_id = order.buyer_id, order.supplier_id

            # Vérifier les autorisations selon le statut
            if data.new_status == OrderStatus.CONFIRMED:
                if order.supplier_id != user_id:
                    raise BusinessRuleError("Seul le fournisseur peut confirmer la commande")

            elif data.new_status in [OrderStatus.CANCELLED]:
                if order.buyer_id != user_id and order.supplier_id != user_id:
                    raise BusinessRuleError("Non autorisé")

            # Vérifier la transition de statut
            self._validate_status_transition(order.status, data.new_status)

            # Mettre à jour le statut
            old_status = order.status
            self.order_repo.update(data.order_id, status=data.new_status)

            # Créer l'historique
            self.order_history_repo.create(
                order_id=data.order_id,
                old_status=old_status,
                new_status=data.new_status,
                comment=data.comment,
                changed_by=user_id
            )

            logger.info(f"Statut commande {data.order_id}: {old_status} -> {data.new_status}")

            # Récupérer la commande mise à jour
            order = self.order_repo.get_by_id(data.order_id)

            # Prévenir la partie opposée. `notify_order_status_changed` résout le
            # destinataire à partir de l'auteur et se tait sur les statuts sans
            # message dédié (`processing`).
            await self._notify(
                lambda svc: svc.notify_order_status_changed(
                    order_id=data.order_id,
                    new_status=data.new_status.value,
                    buyer_id=buyer_id,
                    supplier_id=supplier_id,
                    actor_id=user_id,
                    tracking_number=order.tracking_number,
                    reason=data.comment,
                )
            )

            order_schema = OrderMapper.entity_to_schema(order)
            order_schema = self._enrich_order(order_schema)

            return ResponseBase[OrderSchema](
                success=True,
                message="Statut de la commande mis à jour",
                item=order_schema
            )

        except (NotFoundError, BusinessRuleError, ValidationError):
            raise
        except Exception as e:
            logger.error(f"Erreur mise à jour statut: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def _validate_status_transition(self, current: OrderStatus, new: OrderStatus):
        """Valider qu'une transition de statut est autorisée"""
        # Flux fournisseur (fulfillment) : confirmer -> expédier -> livrer. Les
        # étapes PAID/PROCESSING restent valides (paiement mocké), mais on
        # autorise aussi le raccourci CONFIRMED -> PROCESSING/SHIPPED car l'app
        # n'expose pas d'UI pour marquer "payée"/"en préparation".
        valid_transitions = {
            OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
            OrderStatus.CONFIRMED: [
                OrderStatus.PAID,
                OrderStatus.PROCESSING,
                OrderStatus.SHIPPED,
                OrderStatus.CANCELLED,
            ],
            OrderStatus.PAID: [OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.CANCELLED],
            OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
            OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
            OrderStatus.DELIVERED: [OrderStatus.REFUNDED],
            OrderStatus.CANCELLED: [],
            OrderStatus.REFUNDED: [],
        }

        if new not in valid_transitions.get(current, []):
            raise BusinessRuleError(
                f"Transition de statut invalide: {current.value} -> {new.value}"
            )

    async def cancel_order(self, user_id: int, data: CancelOrderSchema) -> ResponseBase[OrderSchema]:
        """Annuler une commande"""
        try:
            order = self.order_repo.get_by_id(data.order_id)
            if not order:
                raise NotFoundError("Commande non trouvée")

            # Vérifier que l'utilisateur peut annuler
            if order.buyer_id != user_id and order.supplier_id != user_id:
                raise BusinessRuleError("Non autorisé")

            buyer_id, supplier_id = order.buyer_id, order.supplier_id

            # Vérifier que la commande peut être annulée
            if order.status not in [OrderStatus.PENDING, OrderStatus.CONFIRMED]:
                raise BusinessRuleError("Cette commande ne peut plus être annulée")

            # Remettre les produits en stock
            for item in order.order_items:
                product = self.product_repo.get_by_id(item.product_id)
                if product:
                    new_stock = product.stock_quantity + item.quantity
                    self.product_repo.update(product.id, stock_quantity=new_stock)

            # Annuler la commande
            self.order_repo.update(
                data.order_id,
                status=OrderStatus.CANCELLED,
                cancellation_reason=data.cancellation_reason
            )

            # Historique
            self.order_history_repo.create(
                order_id=data.order_id,
                old_status=order.status,
                new_status=OrderStatus.CANCELLED,
                comment=f"Annulation: {data.cancellation_reason}",
                changed_by=user_id
            )

            logger.info(f"Commande {data.order_id} annulée")

            await self._notify(
                lambda svc: svc.notify_order_status_changed(
                    order_id=data.order_id,
                    new_status=OrderStatus.CANCELLED.value,
                    buyer_id=buyer_id,
                    supplier_id=supplier_id,
                    actor_id=user_id,
                    reason=data.cancellation_reason,
                )
            )

            order = self.order_repo.get_by_id(data.order_id)
            order_schema = OrderMapper.entity_to_schema(order)

            return ResponseBase[OrderSchema](
                success=True,
                message="Commande annulée avec succès",
                item=order_schema
            )

        except (NotFoundError, BusinessRuleError):
            raise
        except Exception as e:
            logger.error(f"Erreur annulation commande: {e}")
            raise Exception(f"Erreur: {str(e)}")

    def _enrich_order(self, order_schema: OrderSchema) -> OrderSchema:
        """Enrichir la commande avec les informations supplémentaires"""
        order_schema.items_count = len(order_schema.order_items)
        return order_schema