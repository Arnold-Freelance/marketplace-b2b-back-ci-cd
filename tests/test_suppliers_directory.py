"""Tests d'intégration — annuaire public des fournisseurs (GET /api/v1/suppliers).

Vérifie sur l'app RÉELLE (SQLite en mémoire) que :
- la route est accessible SANS token (vue acheteur anonyme) ;
- les agrégats (produits actifs, note moyenne, nombre d'avis) sont exacts ;
- le tri est « vérifiés d'abord, puis les mieux notés, puis les mieux fournis » ;
- les filtres `search` / `city` et la pagination fonctionnent ;
- un compte fournisseur par `user_roles` (T5) est listé même si son `user_type`
  historique dit autre chose.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.enums import UserStatus, UserType


@pytest.fixture
def db_and_client():
    """TestClient sur l'app réelle + session pour semer la base."""
    from app.main_new import app
    from app.db.base import Base
    from app.api import deps

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def _get_db_override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[deps.get_db] = _get_db_override
    seed_session = TestingSessionLocal()
    try:
        yield seed_session, TestClient(app)
    finally:
        seed_session.close()
        app.dependency_overrides.pop(deps.get_db, None)
        Base.metadata.drop_all(bind=engine)


def _user(db, *, uid, email, user_type=UserType.supplier, status=UserStatus.active):
    from app.models.user_entity import UserEntity

    user = UserEntity(
        id=uid,
        email=email,
        phone=f"+2250000000{uid:02d}",
        password_hash="x",
        user_type=user_type,
        status=status,
    )
    db.add(user)
    return user


def _profile(db, *, uid, company_name, city="Abidjan", is_verified=False):
    from app.models.company_profile_entity import CompanyProfileEntity

    db.add(
        CompanyProfileEntity(
            user_id=uid,
            company_name=company_name,
            city=city,
            is_verified=is_verified,
        )
    )


def _product(db, *, pid, supplier_id, is_active=True, is_deleted=False):
    from app.models.product_entity import ProductEntity

    db.add(
        ProductEntity(
            id=pid,
            supplier_id=supplier_id,
            name=f"Produit {pid}",
            slug=f"produit-{pid}",
            price=1000,
            is_active=is_active,
            is_deleted=is_deleted,
        )
    )


def _review(db, *, rid, reviewed_id, rating, is_public=True, is_deleted=False):
    from app.models.review_entity import ReviewEntity

    db.add(
        ReviewEntity(
            id=rid,
            order_id=rid,
            reviewer_id=99,
            reviewed_id=reviewed_id,
            rating=rating,
            is_public=is_public,
            is_deleted=is_deleted,
        )
    )


@pytest.fixture
def seeded(db_and_client):
    """
    1 · Adjamé Électro Pro — vérifié, 2 produits actifs (+1 inactif, +1 supprimé), avis 5 et 4
    2 · Grenier d'Abidjan  — non vérifié, 1 produit, avis 5 (public) + 1 avis masqué
    3 · Phone Plus CI      — non vérifié, 0 produit, 0 avis
    4 · Roles Only SARL    — user_type=buyer mais rôle `supplier` en table (T5)
    5 · Banni SA           — suspendu, ne doit jamais apparaître
    6 · Bouaké Frais       — vérifié, ville différente
    """
    from app.models.user_role_entity import UserRoleEntity

    db, client = db_and_client

    _user(db, uid=1, email="adjame@x.ci")
    _profile(db, uid=1, company_name="Adjamé Électro Pro", is_verified=True)
    _product(db, pid=1, supplier_id=1)
    _product(db, pid=2, supplier_id=1)
    _product(db, pid=3, supplier_id=1, is_active=False)
    _product(db, pid=4, supplier_id=1, is_deleted=True)
    _review(db, rid=1, reviewed_id=1, rating=5)
    _review(db, rid=2, reviewed_id=1, rating=4)

    _user(db, uid=2, email="grenier@x.ci")
    _profile(db, uid=2, company_name="Grenier d'Abidjan")
    _product(db, pid=5, supplier_id=2)
    _review(db, rid=3, reviewed_id=2, rating=5)
    _review(db, rid=4, reviewed_id=2, rating=1, is_public=False)

    _user(db, uid=3, email="phone@x.ci")
    _profile(db, uid=3, company_name="Phone Plus CI")

    _user(db, uid=4, email="rolesonly@x.ci", user_type=UserType.buyer)
    _profile(db, uid=4, company_name="Roles Only SARL")
    db.add(UserRoleEntity(user_id=4, role="supplier"))

    _user(db, uid=5, email="banni@x.ci", status=UserStatus.suspended)
    _profile(db, uid=5, company_name="Banni SA", is_verified=True)

    _user(db, uid=6, email="bouake@x.ci")
    _profile(db, uid=6, company_name="Bouaké Frais", city="Bouaké", is_verified=True)

    db.commit()
    return client


def _names(payload):
    return [i["company_name"] for i in payload["items"]]


class TestSuppliersDirectory:
    def test_is_public(self, seeded):
        assert seeded.get("/api/v1/suppliers").status_code == 200

    def test_excludes_suspended_accounts(self, seeded):
        body = seeded.get("/api/v1/suppliers").json()
        assert "Banni SA" not in _names(body)

    def test_includes_supplier_by_role_table(self, seeded):
        """T5 : le rôle vit dans `user_roles`, pas seulement dans `user_type`."""
        body = seeded.get("/api/v1/suppliers").json()
        assert "Roles Only SARL" in _names(body)

    def test_total_counts_only_visible_suppliers(self, seeded):
        body = seeded.get("/api/v1/suppliers").json()
        assert body["total"] == 5  # 6 semés - 1 suspendu

    def test_product_count_ignores_inactive_and_deleted(self, seeded):
        body = seeded.get("/api/v1/suppliers").json()
        adjame = next(i for i in body["items"] if i["company_name"] == "Adjamé Électro Pro")
        assert adjame["product_count"] == 2  # 4 produits, 1 inactif + 1 supprimé écartés

    def test_rating_is_average_of_public_reviews(self, seeded):
        body = seeded.get("/api/v1/suppliers").json()
        by_name = {i["company_name"]: i for i in body["items"]}

        assert by_name["Adjamé Électro Pro"]["average_rating"] == 4.5  # (5+4)/2
        assert by_name["Adjamé Électro Pro"]["total_reviews"] == 2

        # L'avis masqué (is_public=False) ne compte pas.
        assert by_name["Grenier d'Abidjan"]["average_rating"] == 5.0
        assert by_name["Grenier d'Abidjan"]["total_reviews"] == 1

    def test_supplier_without_reviews_has_zero_rating(self, seeded):
        body = seeded.get("/api/v1/suppliers").json()
        phone = next(i for i in body["items"] if i["company_name"] == "Phone Plus CI")
        assert phone["average_rating"] == 0
        assert phone["total_reviews"] == 0
        assert phone["product_count"] == 0

    def test_verified_suppliers_come_first(self, seeded):
        names = _names(seeded.get("/api/v1/suppliers").json())
        verified = {"Adjamé Électro Pro", "Bouaké Frais"}
        first_two = set(names[:2])
        assert first_two == verified, names

    def test_search_filters_on_company_name(self, seeded):
        body = seeded.get("/api/v1/suppliers", params={"search": "grenier"}).json()
        assert _names(body) == ["Grenier d'Abidjan"]
        assert body["total"] == 1

    def test_city_filter(self, seeded):
        body = seeded.get("/api/v1/suppliers", params={"city": "Bouaké"}).json()
        assert _names(body) == ["Bouaké Frais"]

    def test_pagination(self, seeded):
        page1 = seeded.get("/api/v1/suppliers", params={"limit": 2, "offset": 0}).json()
        page2 = seeded.get("/api/v1/suppliers", params={"limit": 2, "offset": 2}).json()

        assert len(page1["items"]) == 2
        assert len(page2["items"]) == 2
        # `total` reste le total absolu, pas la taille de page.
        assert page1["total"] == page2["total"] == 5
        assert set(_names(page1)).isdisjoint(_names(page2))

    def test_limit_is_bounded(self, seeded):
        assert seeded.get("/api/v1/suppliers", params={"limit": 0}).status_code == 422
        assert seeded.get("/api/v1/suppliers", params={"limit": 500}).status_code == 422

    def test_detail_route_still_reachable(self, seeded):
        """La route liste ne doit pas masquer `/suppliers/{id}`."""
        assert seeded.get("/api/v1/suppliers/1").status_code == 200
