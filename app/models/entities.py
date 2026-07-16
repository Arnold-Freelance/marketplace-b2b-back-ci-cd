# ============================================================================
# ENTITIES (SQLALCHEMY MODELS)
# ============================================================================
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Numeric, JSON, ForeignKey, Enum as SQLEnum
from app.core.enums import *
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

# class UserEntity(Base):
#     __tablename__ = "users"
#
#     id = Column(Integer, primary_key=True, index=True)
#     email = Column(String(255), unique=True, nullable=False, index=True)
#     phone = Column(String(20), unique=True, nullable=False, index=True)
#     password_hash = Column(String(255), nullable=False)
#     user_type = Column(SQLEnum(UserType), nullable=False)
#     status = Column(SQLEnum(UserStatus), nullable=False)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
#     last_login = Column(DateTime(timezone=True))
#     email_verified = Column(Boolean, default=False)
#     phone_verified = Column(Boolean, default=False)
#
#     # Relations
#     company_profile = relationship("CompanyProfileEntity", back_populates="user", uselist=False)
#     products = relationship("ProductEntity", back_populates="supplier")
#     buyer_orders = relationship("OrderEntity", foreign_keys="OrderEntity.buyer_id", back_populates="buyer")
#     supplier_orders = relationship("OrderEntity", foreign_keys="OrderEntity.supplier_id", back_populates="supplier")


# class CompanyProfileEntity(Base):
#     __tablename__ = "company_profiles"
#
#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
#     company_name = Column(String(255), nullable=False)
#
#     business_registration = Column(String(100))
#     company_description = Column(Text)
#     contact_person = Column(String(255))
#     address = Column(Text)
#     city = Column(String(100))
#     district = Column(String(100))
#     is_verified = Column(Boolean, default=False)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
#
#     # Relations
#     user = relationship("UserEntity", back_populates="company_profile")




# class ProductEntity(Base):
#     __tablename__ = "products"
#
#     id = Column(Integer, primary_key=True, index=True)
#     supplier_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
#     category_id = Column(Integer, ForeignKey("categories.id"))
#     name = Column(String(255), nullable=False)
#     slug = Column(String(255), nullable=False)
#     description = Column(Text)
#     short_description = Column(String(500))
#     sku = Column(String(100))
#     price = Column(Numeric(10, 2), nullable=False)
#     currency = Column(String(3), default="XOF")
#     min_order_quantity = Column(Integer, default=1)
#     stock_quantity = Column(Integer, default=0)
#     unit = Column(String(50))
#     images = Column(JSON)
#     attributes = Column(JSON)
#     is_active = Column(Boolean, default=True)
#     is_featured = Column(Boolean, default=False)
#     views_count = Column(Integer, default=0)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
#
#     # Relations
#     supplier = relationship("UserEntity", back_populates="products")
#     category = relationship("CategoryEntity", back_populates="products")


class OrderEntity(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="XOF")
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
    shipping_address = Column(JSON)
    buyer_notes = Column(Text)
    supplier_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    buyer = relationship("UserEntity", foreign_keys=[buyer_id], back_populates="buyer_orders")
    supplier = relationship("UserEntity", foreign_keys=[supplier_id], back_populates="supplier_orders")