# app/models/user_role_entity.py
"""Entité rôle utilisateur (T5).

Un compte utilisateur porte une **liste de rôles** (`buyer`, `supplier`,
`admin`). Un supplier possède automatiquement aussi `buyer`. La bascule
d'espace supplier ↔ buyer est un simple changement de contexte côté frontend ;
côté backend, les guards vérifient la **présence** du rôle requis dans le JWT.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserRoleEntity(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Valeurs attendues : "buyer" | "supplier" | "admin" (cf. UserType).
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserEntity", back_populates="roles")
