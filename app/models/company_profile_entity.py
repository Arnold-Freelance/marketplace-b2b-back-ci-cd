# app/models/company_profile_entity.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Numeric
from sqlalchemy.orm import relationship
from app.db.base import Base
from sqlalchemy.sql import func


# class CompanyProfileEntity(Base):
#     """Profil entreprise associé à un utilisateur"""
#     __tablename__ = "company_profiles"
#
#     id = Column(Integer, primary_key=True)
#     user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
#     company_name = Column(String(255), nullable=False)
#     contact_person = Column(String(255))
#     city = Column(String(100))
#
#     # Autres champs possibles
#     address = Column(String(500))
#     postal_code = Column(String(20))
#     country = Column(String(100))
#
#     # Relation
#     user = relationship("UserEntity", back_populates="company_profile")



class CompanyProfileEntity(Base):
    __tablename__ = "company_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    company_name = Column(String(255), nullable=False)

    business_registration = Column(String(100))
    company_description = Column(Text)
    contact_person = Column(String(255))
    address = Column(Text)
    city = Column(String(100))
    district = Column(String(100))
    region = Column(String(100))
    tax_id = Column(String(100))
    phone = Column(String(30))
    whatsapp = Column(String(30))
    facebook = Column(String(255))
    instagram = Column(String(255))
    is_verified = Column(Boolean, default=False)

    # Barème de livraison du fournisseur (une commande = un fournisseur, cf.
    # order_service.create_order_from_cart qui scinde le panier).
    shipping_base_cost = Column(Numeric(10, 2), nullable=False, server_default="0")
    # Franco de port : au-delà de ce sous-total, la livraison est offerte.
    # Nul = pas de franco, le barème de base s'applique toujours.
    free_shipping_threshold = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    user = relationship("UserEntity", back_populates="company_profile")