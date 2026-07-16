"""Tests T3 — panier invité : fusion + addition des quantités.

Couvre :
- correction du bug `add_to_cart` (les quantités s'ADDITIONNENT, ne se
  soustraient plus) ;
- `merge_guest_cart` : addition par produit + dédoublonnage, plafonnement au
  stock, articles indisponibles (inactif / rupture / inexistant) ignorés.

Test DB réel (SQLite en mémoire) exerçant `CartService` avec ses vrais repos.
"""
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main_new  # noqa: F401 — charge toutes les entités
from app.db.base import Base
from app.core.enums import UserType
from app.models.user_entity import UserEntity
from app.models.category_entity import CategoryEntity
from app.models.product_entity import ProductEntity
from app.repositories.cart_repo import CartRepository, CartItemRepository
from app.repositories.product_repo import ProductRepository
from app.schemas.cart import AddToCartSchema, MergeCartItemSchema
from app.services.cart_service import CartService


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


def _user(db, email, phone, user_type):
    u = UserEntity(email=email, phone=phone, password_hash="x", user_type=user_type, status="active")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _product(db, supplier_id, cat_id, slug, stock, active=True, price="1000"):
    p = ProductEntity(
        supplier_id=supplier_id, category_id=cat_id, name="P " + slug, slug=slug,
        price=Decimal(price), stock_quantity=stock, is_active=active, is_deleted=False,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def ctx(db):
    buyer = _user(db, "buy@t.ci", "+2250101", UserType.buyer)
    supplier = _user(db, "sup@t.ci", "+2250102", UserType.supplier)
    cat = CategoryEntity(name="Cat", slug="cat")
    db.add(cat)
    db.commit()
    db.refresh(cat)
    service = CartService(CartRepository(db), CartItemRepository(db), ProductRepository(db))
    return {
        "db": db, "service": service, "buyer": buyer.id, "supplier": supplier.id, "cat": cat.id,
        "cart_repo": CartRepository(db), "item_repo": CartItemRepository(db),
    }


def _qty(ctx, product_id):
    cart = ctx["cart_repo"].get_active_cart(ctx["buyer"])
    if not cart:
        return None
    item = ctx["item_repo"].get_by_cart_and_product(cart.id, product_id)
    return item.quantity if item else None


# --------------------------------------------------------------------------- #
# add_to_cart : addition (correction de bug)
# --------------------------------------------------------------------------- #
def test_add_to_cart_accumulates_quantity(ctx):
    p = _product(ctx["db"], ctx["supplier"], ctx["cat"], "acc", stock=50)
    ctx["service"].add_to_cart(ctx["buyer"], AddToCartSchema(product_id=p.id, quantity=2))
    ctx["service"].add_to_cart(ctx["buyer"], AddToCartSchema(product_id=p.id, quantity=3))
    assert _qty(ctx, p.id) == 5  # 2 + 3, plus de soustraction


# --------------------------------------------------------------------------- #
# merge_guest_cart
# --------------------------------------------------------------------------- #
def test_merge_into_empty_cart(ctx):
    a = _product(ctx["db"], ctx["supplier"], ctx["cat"], "a", stock=10)
    b = _product(ctx["db"], ctx["supplier"], ctx["cat"], "b", stock=10)
    ctx["service"].merge_guest_cart(ctx["buyer"], [
        MergeCartItemSchema(product_id=a.id, quantity=2),
        MergeCartItemSchema(product_id=b.id, quantity=1),
    ])
    assert _qty(ctx, a.id) == 2
    assert _qty(ctx, b.id) == 1


def test_merge_adds_to_existing_and_dedups(ctx):
    a = _product(ctx["db"], ctx["supplier"], ctx["cat"], "a", stock=10)
    b = _product(ctx["db"], ctx["supplier"], ctx["cat"], "b", stock=10)
    # Panier serveur pré-existant : A=2.
    ctx["service"].add_to_cart(ctx["buyer"], AddToCartSchema(product_id=a.id, quantity=2))
    # Invité : A=3 (doit s'additionner → 5), B=1 (nouveau).
    ctx["service"].merge_guest_cart(ctx["buyer"], [
        MergeCartItemSchema(product_id=a.id, quantity=3),
        MergeCartItemSchema(product_id=b.id, quantity=1),
    ])
    assert _qty(ctx, a.id) == 5
    assert _qty(ctx, b.id) == 1


def test_merge_caps_at_stock(ctx):
    a = _product(ctx["db"], ctx["supplier"], ctx["cat"], "a", stock=4)
    ctx["service"].merge_guest_cart(ctx["buyer"], [
        MergeCartItemSchema(product_id=a.id, quantity=10),
    ])
    assert _qty(ctx, a.id) == 4  # plafonné au stock


def test_merge_skips_inactive_and_out_of_stock(ctx):
    inactive = _product(ctx["db"], ctx["supplier"], ctx["cat"], "inact", stock=10, active=False)
    empty = _product(ctx["db"], ctx["supplier"], ctx["cat"], "empty", stock=0)
    ok = _product(ctx["db"], ctx["supplier"], ctx["cat"], "ok", stock=5)
    resp = ctx["service"].merge_guest_cart(ctx["buyer"], [
        MergeCartItemSchema(product_id=inactive.id, quantity=1),
        MergeCartItemSchema(product_id=empty.id, quantity=1),
        MergeCartItemSchema(product_id=ok.id, quantity=2),
        MergeCartItemSchema(product_id=999999, quantity=1),  # inexistant
    ])
    assert _qty(ctx, inactive.id) is None
    assert _qty(ctx, empty.id) is None
    assert _qty(ctx, ok.id) == 2
    assert resp.success is True  # jamais d'échec global
