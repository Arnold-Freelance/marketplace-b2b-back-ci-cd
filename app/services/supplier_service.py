"""
SupplierService — agrégations fournisseur.

- `get_dashboard`  : indicateurs du tableau de bord (produits actifs, stock
  faible, commandes, clients, revenu du mois) + commandes récentes + top
  produits + revenu par mois.
- `list_public`    : annuaire public des fournisseurs (vue acheteur).
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import distinct, extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import UserStatus, UserType
from app.models.company_profile_entity import CompanyProfileEntity
from app.models.order_entity import OrderEntity
from app.models.product_entity import ProductEntity
from app.models.review_entity import ReviewEntity
from app.models.user_entity import UserEntity
from app.models.user_role_entity import UserRoleEntity
from app.mappers.order_mapper import OrderMapper
from app.mappers.product_mapper import ProductMapper

LOW_STOCK_THRESHOLD = 5

# Un compte est fournisseur soit par son `user_type` historique, soit par une
# ligne dans `user_roles` (T5, rôles multiples). On accepte les deux.
_HIDDEN_STATUSES = (UserStatus.suspended, UserStatus.inactive)


class SupplierService:
    def __init__(self, db: Session):
        self.db = db

    def list_public(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        search: Optional[str] = None,
        city: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """
        Annuaire public des fournisseurs, avec nombre de produits actifs et
        réputation agrégés en une seule requête (pas de N+1).

        La note est la moyenne des avis reçus (`reviews.reviewed_id`), pas celle
        des produits : c'est la réputation du vendeur.
        """
        db = self.db

        product_counts = (
            db.query(
                ProductEntity.supplier_id.label("supplier_id"),
                func.count(ProductEntity.id).label("product_count"),
            )
            .filter(
                ProductEntity.is_active.is_(True),
                ProductEntity.is_deleted.is_(False),
            )
            .group_by(ProductEntity.supplier_id)
            .subquery()
        )

        reputation = (
            db.query(
                ReviewEntity.reviewed_id.label("supplier_id"),
                func.avg(ReviewEntity.rating).label("average_rating"),
                func.count(ReviewEntity.id).label("total_reviews"),
            )
            .filter(
                ReviewEntity.is_public.is_(True),
                ReviewEntity.is_deleted.is_(False),
            )
            .group_by(ReviewEntity.reviewed_id)
            .subquery()
        )

        supplier_role_ids = select(UserRoleEntity.user_id).where(
            UserRoleEntity.role == UserType.supplier.value
        )

        product_count = func.coalesce(product_counts.c.product_count, 0)
        average_rating = func.coalesce(reputation.c.average_rating, 0.0)
        total_reviews = func.coalesce(reputation.c.total_reviews, 0)

        query = (
            db.query(UserEntity, CompanyProfileEntity, product_count, average_rating, total_reviews)
            .outerjoin(CompanyProfileEntity, CompanyProfileEntity.user_id == UserEntity.id)
            .outerjoin(product_counts, product_counts.c.supplier_id == UserEntity.id)
            .outerjoin(reputation, reputation.c.supplier_id == UserEntity.id)
            .filter(
                UserEntity.status.notin_(_HIDDEN_STATUSES),
                or_(
                    UserEntity.user_type == UserType.supplier,
                    UserEntity.id.in_(supplier_role_ids),
                ),
            )
        )

        if search:
            query = query.filter(CompanyProfileEntity.company_name.ilike(f"%{search.strip()}%"))
        if city:
            query = query.filter(CompanyProfileEntity.city.ilike(city.strip()))

        total = query.count()

        rows = (
            query.order_by(
                func.coalesce(CompanyProfileEntity.is_verified, False).desc(),
                average_rating.desc(),
                product_count.desc(),
                UserEntity.id.asc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [
            {
                "id": user.id,
                "email": user.email,
                "phone": user.phone,
                "company_name": profile.company_name if profile else None,
                "company_description": getattr(profile, "company_description", None) if profile else None,
                "contact_person": profile.contact_person if profile else None,
                "address": getattr(profile, "address", None) if profile else None,
                "city": profile.city if profile else None,
                "is_verified": bool(profile.is_verified) if profile else False,
                "average_rating": round(float(rating or 0), 2),
                "total_reviews": int(reviews or 0),
                "product_count": int(count or 0),
            }
            for user, profile, count, rating, reviews in rows
        ]

        return items, int(total or 0)

    def get_dashboard(self, supplier_id: int) -> dict:
        db = self.db

        active_products = (
            db.query(func.count(ProductEntity.id))
            .filter(
                ProductEntity.supplier_id == supplier_id,
                ProductEntity.is_active.is_(True),
                ProductEntity.is_deleted.is_(False),
            )
            .scalar()
        )
        low_stock = (
            db.query(func.count(ProductEntity.id))
            .filter(
                ProductEntity.supplier_id == supplier_id,
                ProductEntity.is_deleted.is_(False),
                ProductEntity.stock_quantity < LOW_STOCK_THRESHOLD,
            )
            .scalar()
        )
        total_orders = (
            db.query(func.count(OrderEntity.id))
            .filter(OrderEntity.supplier_id == supplier_id)
            .scalar()
        )
        total_customers = (
            db.query(func.count(distinct(OrderEntity.buyer_id)))
            .filter(OrderEntity.supplier_id == supplier_id)
            .scalar()
        )

        now = datetime.now(timezone.utc)
        monthly_revenue = (
            db.query(func.coalesce(func.sum(OrderEntity.total_amount), 0))
            .filter(
                OrderEntity.supplier_id == supplier_id,
                extract("year", OrderEntity.created_at) == now.year,
                extract("month", OrderEntity.created_at) == now.month,
            )
            .scalar()
        )

        recent_orders = (
            db.query(OrderEntity)
            .filter(OrderEntity.supplier_id == supplier_id)
            .order_by(OrderEntity.created_at.desc())
            .limit(5)
            .all()
        )
        top_products = (
            db.query(ProductEntity)
            .filter(
                ProductEntity.supplier_id == supplier_id,
                ProductEntity.is_deleted.is_(False),
            )
            .order_by(ProductEntity.views_count.desc())
            .limit(5)
            .all()
        )

        # Revenu par mois (6 derniers mois) — groupé année/mois
        revenue_rows = (
            db.query(
                extract("year", OrderEntity.created_at).label("y"),
                extract("month", OrderEntity.created_at).label("m"),
                func.coalesce(func.sum(OrderEntity.total_amount), 0).label("rev"),
            )
            .filter(OrderEntity.supplier_id == supplier_id)
            .group_by("y", "m")
            .order_by("y", "m")
            .limit(6)
            .all()
        )
        revenue_data = [
            {"year": int(r.y), "month": int(r.m), "revenue": float(r.rev or 0)}
            for r in revenue_rows
        ]

        return {
            "stats": {
                "monthlyRevenue": float(monthly_revenue or 0),
                "totalOrders": int(total_orders or 0),
                "activeProducts": int(active_products or 0),
                "totalCustomers": int(total_customers or 0),
                "lowStockProducts": int(low_stock or 0),
            },
            "recentOrders": [OrderMapper.entity_to_schema(o) for o in recent_orders],
            "topProducts": [ProductMapper.entity_to_schema(p) for p in top_products],
            "revenueData": revenue_data,
        }
