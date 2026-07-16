# app/models/address_entity.py
"""Carnet d'adresses de livraison de l'acheteur."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class AddressEntity(Base):
    """Adresse de livraison réutilisable.

    Les champs reprennent exactement ceux de `ShippingAddressSchema` : au moment
    de commander, l'adresse choisie est recopiée telle quelle dans
    `orders.shipping_address` (JSON figé). Une adresse modifiée ou supprimée plus
    tard ne réécrit donc pas l'historique des commandes passées.
    """
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    #: Étiquette libre choisie par l'utilisateur (« Entrepôt Yopougon », « Boutique »).
    label = Column(String(100))

    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255))
    city = Column(String(100), nullable=False)
    state = Column(String(100))
    postal_code = Column(String(20))
    # ⚠️ Littéral SQL explicite, apostrophe doublée. Passer la chaîne brute
    # ("Côte d'Ivoire") produit bien le bon DDL, mais `compare_server_default`
    # d'Alembic la réinjecte SANS l'échapper au moment de comparer le modèle à la
    # base — le SQL généré est alors invalide et TOUTE autogénération de migration
    # échoue, même sans rapport avec cette table.
    country = Column(String(100), nullable=False, server_default=text("'Côte d''Ivoire'"))

    #: Repère de proximité — en Côte d'Ivoire, souvent plus utile que la rue.
    landmark = Column(Text)

    is_default = Column(Boolean, nullable=False, server_default="false")
    is_deleted = Column(Boolean, nullable=False, server_default="false")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("UserEntity")
