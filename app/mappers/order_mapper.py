"""
Mapper pour les commandes
"""
from app.models.order_entity import OrderEntity
from app.schemas.order import OrderSchema, OrderItemSchema, OrderStatusHistorySchema


class OrderMapper:
    """Mapper pour les commandes"""

    @staticmethod
    def entity_to_schema(entity: OrderEntity) -> OrderSchema:
        """Convertit OrderEntity vers OrderSchema"""
        if not entity:
            return None

        # Items de la commande
        order_items = []
        if entity.order_items:
            order_items = [
                OrderItemSchema(
                    id=item.id,
                    order_id=item.order_id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    product_sku=item.product_sku,
                    product_image_url=item.product_image_url,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    subtotal=item.subtotal,
                    currency=item.currency,
                    product_attributes=item.product_attributes,
                    created_at=item.created_at.strftime("%d/%m/%Y %H:%M") if item.created_at else None
                )
                for item in entity.order_items
            ]

        # Informations acheteur/fournisseur (le nom vient du profil entreprise,
        # qui peut être None)
        def _display_name(user):
            if not user:
                return None
            profile = getattr(user, "company_profile", None)
            if profile:
                return profile.company_name or profile.contact_person
            return None

        buyer_name = _display_name(entity.buyer)
        buyer_email = entity.buyer.email if entity.buyer else None

        supplier_name = _display_name(entity.supplier)
        supplier_email = entity.supplier.email if entity.supplier else None

        # Moyen de paiement : porté par la table `payments`, pas par la commande.
        # Une commande n'a qu'un paiement à la création ; on prend le dernier
        # pour rester juste le jour où un réessai en ajoutera un second.
        # Tri sur `id` (monotone) et non `created_at`, qui mêle des dates avec et
        # sans fuseau selon le backend SQL et lèverait à la comparaison.
        payments = sorted(entity.payments or [], key=lambda p: p.id)
        last_payment = payments[-1] if payments else None

        # Suivi de livraison, du plus ancien au plus récent (tri par `id`, monotone).
        status_history = [
            OrderStatusHistorySchema(
                id=h.id,
                old_status=h.old_status,
                new_status=h.new_status,
                comment=h.comment,
                created_at=h.created_at.strftime("%d/%m/%Y %H:%M") if h.created_at else None,
            )
            for h in sorted(entity.status_history or [], key=lambda h: h.id)
        ]

        return OrderSchema(
            id=entity.id,
            order_number=entity.order_number,
            buyer_id=entity.buyer_id,
            supplier_id=entity.supplier_id,
            buyer_name=buyer_name,
            buyer_email=buyer_email,
            supplier_name=supplier_name,
            supplier_email=supplier_email,
            subtotal=entity.subtotal,
            shipping_cost=entity.shipping_cost,
            tax_amount=entity.tax_amount,
            discount_amount=entity.discount_amount,
            total_amount=entity.total_amount,
            currency=entity.currency,
            status=entity.status,
            payment_status=entity.payment_status,
            shipping_method=entity.shipping_method,
            shipping_address=entity.shipping_address,
            tracking_number=entity.tracking_number,
            estimated_delivery_date=entity.estimated_delivery_date.strftime(
                "%d/%m/%Y") if entity.estimated_delivery_date else None,
            actual_delivery_date=entity.actual_delivery_date.strftime(
                "%d/%m/%Y") if entity.actual_delivery_date else None,
            buyer_notes=entity.buyer_notes,
            supplier_notes=entity.supplier_notes,
            cancellation_reason=entity.cancellation_reason,
            payment_method=last_payment.payment_method if last_payment else None,
            payment_provider=last_payment.payment_provider if last_payment else None,
            order_items=order_items,
            status_history=status_history,
            created_at=entity.created_at.strftime("%d/%m/%Y %H:%M") if entity.created_at else None,
            updated_at=entity.updated_at.strftime("%d/%m/%Y %H:%M") if entity.updated_at else None
        )