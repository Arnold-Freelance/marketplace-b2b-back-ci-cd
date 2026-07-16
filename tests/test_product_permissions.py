"""Tests T6 — permissions produit & override admin.

Vérifie la cohérence demandée :
- un **supplier** crée/édite **ses** produits ;
- un **admin** peut créer AU NOM d'un fournisseur (`supplier_id` cible) et
  éditer/supprimer/mettre à jour le stock de N'IMPORTE quel produit ;
- un **buyer** ne peut pas créer ; un supplier ne peut pas toucher au produit
  d'un autre ;
- la traçabilité `updated_by` enregistre l'auteur réel (admin ou fournisseur).

Test DB réel (SQLite en mémoire) exerçant `ProductService` avec ses vrais repos.
"""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Importer l'app force le chargement de TOUTES les entités (métadonnées complètes).
import app.main_new  # noqa: F401
from app.db.base import Base
from app.core.enums import UserType
from app.core.exceptions import BusinessRuleError, ValidationError
from app.models.user_entity import UserEntity
from app.models.user_role_entity import UserRoleEntity
from app.models.category_entity import CategoryEntity
from app.repositories.product_repo import ProductRepository
from app.repositories.category_repo import CategoryRepo
from app.repositories.user_repo import UserRepository
from app.repositories.product_image_repo import ProductImageRepository
from app.schemas.base import RequestBase
from app.schemas.product import ProductSchema
from app.services.product_service import ProductService
from app.services.product_image_service import ProductImageService
from app.services.file_upload_service import FileUploadService


# --------------------------------------------------------------------------- #
# Unitaire pur : la règle d'autorisation d'écriture
# --------------------------------------------------------------------------- #
def test_can_write_product_rule():
    can = ProductService._can_write_product
    assert can(5, 5, set()) is True            # propriétaire
    assert can(5, 9, {"admin"}) is True         # admin sur produit d'autrui
    assert can(5, 9, {"buyer"}) is False        # tiers sans droit
    assert can(5, 9, {"supplier"}) is False     # autre fournisseur


# --------------------------------------------------------------------------- #
# Fixtures DB
# --------------------------------------------------------------------------- #
@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(db, email, phone, user_type, roles):
    u = UserEntity(
        email=email, phone=phone, password_hash="x",
        user_type=user_type, status="active",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    for r in roles:
        db.add(UserRoleEntity(user_id=u.id, role=r))
    db.commit()
    return u


@pytest.fixture
def ctx(db):
    supplier = _user(db, "sup@t.ci", "+2250101", UserType.supplier, ["buyer", "supplier"])
    supplier2 = _user(db, "sup2@t.ci", "+2250102", UserType.supplier, ["buyer", "supplier"])
    buyer = _user(db, "buy@t.ci", "+2250103", UserType.buyer, ["buyer"])
    admin = _user(db, "adm@t.ci", "+2250104", UserType.admin, ["admin"])
    cat = CategoryEntity(name="Cat", slug="cat")
    db.add(cat)
    db.commit()
    db.refresh(cat)
    service = ProductService(ProductRepository(db), CategoryRepo(db), UserRepository(db))
    return {
        "db": db, "service": service, "cat": cat.id,
        "supplier": supplier.id, "supplier2": supplier2.id,
        "buyer": buyer.id, "admin": admin.id,
    }


def _data(cat_id, slug, supplier_id=None):
    return ProductSchema(
        name="Produit " + slug, slug=slug, category_id=cat_id,
        price=Decimal("1000"), supplier_id=supplier_id,
    )


def _req(user_id, data):
    return RequestBase[ProductSchema](user=user_id, data=data)


def _create(ctx, user_id, slug, supplier_id=None):
    return ctx["service"].create(_req(user_id, _data(ctx["cat"], slug, supplier_id)))


# --------------------------------------------------------------------------- #
# CREATE
# --------------------------------------------------------------------------- #
def test_supplier_creates_own_product(ctx):
    resp = _create(ctx, ctx["supplier"], "sup-own")
    prod = ctx["service"].product_repo.get_by_id(resp.item.id)
    assert prod.supplier_id == ctx["supplier"]
    assert prod.updated_by == ctx["supplier"]


def test_admin_creates_on_behalf_of_supplier(ctx):
    resp = _create(ctx, ctx["admin"], "adm-for-sup", supplier_id=ctx["supplier"])
    prod = ctx["service"].product_repo.get_by_id(resp.item.id)
    assert prod.supplier_id == ctx["supplier"]   # possédé par le fournisseur cible
    assert prod.updated_by == ctx["admin"]       # mais tracé comme créé par l'admin


def test_admin_create_without_supplier_id_is_rejected(ctx):
    with pytest.raises(ValidationError):
        _create(ctx, ctx["admin"], "adm-no-target")


def test_admin_create_target_not_supplier_is_rejected(ctx):
    with pytest.raises(BusinessRuleError):
        _create(ctx, ctx["admin"], "adm-bad-target", supplier_id=ctx["buyer"])


def test_buyer_cannot_create_product(ctx):
    with pytest.raises(BusinessRuleError):
        _create(ctx, ctx["buyer"], "buyer-try")


# --------------------------------------------------------------------------- #
# UPDATE / DELETE / STOCK
# --------------------------------------------------------------------------- #
def test_admin_can_update_any_product(ctx):
    pid = _create(ctx, ctx["supplier"], "to-edit").item.id
    ctx["service"].update(_req(ctx["admin"], ProductSchema(id=pid, name="Renommé")))
    prod = ctx["service"].product_repo.get_by_id(pid)
    assert prod.name == "Renommé"
    assert prod.updated_by == ctx["admin"]        # trace l'admin
    assert prod.supplier_id == ctx["supplier"]    # propriétaire inchangé


def test_other_supplier_cannot_update(ctx):
    pid = _create(ctx, ctx["supplier"], "to-protect").item.id
    with pytest.raises(BusinessRuleError):
        ctx["service"].update(_req(ctx["supplier2"], ProductSchema(id=pid, name="Piraté")))


def test_admin_can_delete_any_product(ctx):
    pid = _create(ctx, ctx["supplier"], "to-delete").item.id
    ctx["service"].delete(_req(ctx["admin"], ProductSchema(id=pid)))
    prod = ctx["service"].product_repo.get_by_id(pid)
    assert prod.is_deleted is True


def test_admin_can_update_stock(ctx):
    pid = _create(ctx, ctx["supplier"], "to-stock").item.id
    ctx["service"].update_stock(pid, 50, ctx["admin"])
    prod = ctx["service"].product_repo.get_by_id(pid)
    assert prod.stock_quantity == 50
    assert prod.updated_by == ctx["admin"]


# --------------------------------------------------------------------------- #
# IMAGES PRODUIT — autorisation (propriétaire OU admin)
# --------------------------------------------------------------------------- #
def _image_service(ctx):
    db = ctx["db"]
    return ProductImageService(
        ProductImageRepository(db),
        ProductRepository(db),
        FileUploadService(base_upload_dir="uploads"),
        UserRepository(db),
    )


def test_image_owner_and_admin_can_manage(ctx):
    pid = _create(ctx, ctx["supplier"], "img-ok").item.id
    svc = _image_service(ctx)
    # reorder vide = no-op côté repo ; ce qu'on teste, c'est l'autorisation.
    assert svc.reorder_images(pid, {}, ctx["supplier"]) is True   # propriétaire
    assert svc.reorder_images(pid, {}, ctx["admin"]) is True       # admin


def test_image_other_supplier_forbidden(ctx):
    pid = _create(ctx, ctx["supplier"], "img-prot").item.id
    svc = _image_service(ctx)
    with pytest.raises(HTTPException) as e:
        svc.reorder_images(pid, {}, ctx["supplier2"])
    assert e.value.status_code == 403


def test_image_buyer_forbidden(ctx):
    pid = _create(ctx, ctx["supplier"], "img-buyer").item.id
    svc = _image_service(ctx)
    with pytest.raises(HTTPException) as e:
        svc.set_primary_image(1, pid, ctx["buyer"])
    assert e.value.status_code == 403


def test_image_manage_unknown_product_404(ctx):
    svc = _image_service(ctx)
    with pytest.raises(HTTPException) as e:
        svc.reorder_images(999999, {}, ctx["admin"])
    assert e.value.status_code == 404
