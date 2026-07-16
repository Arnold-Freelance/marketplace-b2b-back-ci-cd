# app/models/password_reset_code_entity.py
"""Codes de réinitialisation de mot de passe (6 chiffres, envoyés par email).

Pourquoi une table plutôt qu'un JWT : un JWT ne se recopie pas à la main. Le
flux mobile demande à l'utilisateur de saisir un code court, il faut donc le
conserver côté serveur pour le vérifier.

Un code est un SECRET au même titre qu'un mot de passe : il est stocké haché
(bcrypt), jamais en clair. Une fuite de la base ne doit pas permettre de prendre
la main sur des comptes.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class PasswordResetCodeEntity(Base):
    """Un code de réinitialisation à usage unique."""
    __tablename__ = "password_reset_codes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    #: Hash bcrypt du code à 6 chiffres. Jamais le code en clair.
    code_hash = Column(String(255), nullable=False)

    expires_at = Column(DateTime(timezone=True), nullable=False)
    #: Renseigné dès que le code a servi — un code ne vaut que pour une remise à zéro.
    used_at = Column(DateTime(timezone=True), nullable=True)

    #: Un code à 6 chiffres, c'est 1 chance sur 1 000 000 — mais 1 sur 1 000 après
    #: 1000 essais. On plafonne donc les tentatives, sans quoi le code serait
    #: cassable par force brute en quelques minutes.
    attempts = Column(Integer, nullable=False, default=0)

    #: Un code invalidé (nouvelle demande, trop d'essais) ne doit plus jamais passer.
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("UserEntity")
