from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship

from app.db.base import Base

class CategoryEntity(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"))
    description = Column(String)
    icon_url = Column(String)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)
    created_by = Column(Integer)
    updated_by = Column(Integer)

    #Relations
    #parent = relationship("CategoryEntity", back_populates="parent")
    parent = relationship("CategoryEntity", remote_side=[id], backref="children")
    products = relationship("ProductEntity", back_populates="category")