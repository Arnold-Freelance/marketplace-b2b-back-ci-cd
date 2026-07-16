"""
Script de seed pour le développement.

Crée un fournisseur de démo, quelques catégories et des produits (dont des
produits "featured") afin de pouvoir tester l'app mobile avec de vraies
données.

Usage (depuis Backend/, venv activé) :
    python -m scripts.seed

Idempotent : ne recrée pas ce qui existe déjà (clé : slug / email).
"""
import app.main_new  # noqa: F401  -> importe toutes les entités via les routers

from app.db.session import SessionLocal
from app.core.enums import UserType, UserStatus
from app.models.user_entity import UserEntity
from app.models.category_entity import CategoryEntity
from app.models.product_entity import ProductEntity
from app.services.auth_service import AuthService


def run():
    # Le schéma est géré par Alembic : exécuter `alembic upgrade head` avant.
    db = SessionLocal()
    try:
        # --- Fournisseur de démo ---
        supplier = db.query(UserEntity).filter(UserEntity.email == "seed.supplier@market.ci").first()
        if not supplier:
            supplier = UserEntity(
                email="seed.supplier@market.ci",
                phone="+2250700000001",
                password_hash=AuthService.hash_password("Passw0rd!"),
                user_type=UserType.supplier,
                status=UserStatus.active,
                email_verified=True,
                phone_verified=True,
            )
            db.add(supplier)
            db.commit()
            db.refresh(supplier)
            print(f"Fournisseur cree (id={supplier.id})")
        else:
            print(f"Fournisseur existant (id={supplier.id})")

        # --- Catégories ---
        categories = [
            {"name": "Téléphones", "slug": "telephone", "icon_url": "📱"},
            {"name": "Informatique", "slug": "informatique", "icon_url": "💻"},
            {"name": "Électroménager", "slug": "electromenager", "icon_url": "🔌"},
        ]
        cat_by_slug = {}
        for c in categories:
            existing = db.query(CategoryEntity).filter(CategoryEntity.slug == c["slug"]).first()
            if not existing:
                existing = CategoryEntity(
                    name=c["name"], slug=c["slug"], icon_url=c["icon_url"], is_active=True
                )
                db.add(existing)
                db.commit()
                db.refresh(existing)
            cat_by_slug[c["slug"]] = existing
        print(f"{len(cat_by_slug)} categories pretes")

        # --- Produits ---
        products = [
            ("iPhone 15 Pro", "iphone-15-pro", "telephone", 1499000, True, 25),
            ("Samsung Galaxy S24", "samsung-galaxy-s24", "telephone", 1199000, True, 40),
            ("Xiaomi Redmi Note 13", "xiaomi-redmi-note-13", "telephone", 189000, False, 120),
            ("MacBook Air M3", "macbook-air-m3", "informatique", 1399000, True, 15),
            ("Dell XPS 13", "dell-xps-13", "informatique", 1099000, False, 10),
            ("Réfrigérateur Samsung", "refrigerateur-samsung", "electromenager", 549000, False, 8),
            ("Climatiseur LG", "climatiseur-lg", "electromenager", 329000, True, 18),
        ]
        created = 0
        for name, slug, cat_slug, price, featured, stock in products:
            if db.query(ProductEntity).filter(ProductEntity.slug == slug).first():
                continue
            db.add(
                ProductEntity(
                    supplier_id=supplier.id,
                    category_id=cat_by_slug[cat_slug].id,
                    name=name,
                    slug=slug,
                    short_description=f"{name} - disponible en gros",
                    description=f"{name}. Produit de démonstration pour le seed.",
                    price=price,
                    currency="XOF",
                    min_order_quantity=1,
                    stock_quantity=stock,
                    unit="pièce",
                    is_active=True,
                    is_featured=featured,
                )
            )
            created += 1
        db.commit()
        print(f"{created} produits crees")
        print("Seed termine.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
