"""Nepal School Management System - Inventory Models"""
import uuid
from datetime import date
from sqlalchemy import Column, String, Boolean, Date, Integer, Text, ForeignKey, Enum as SQLEnum, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


class AssetCategory(str, enum.Enum):
    FURNITURE = "furniture"
    ELECTRONICS = "electronics"
    SPORTS = "sports"
    LAB_EQUIPMENT = "lab_equipment"
    STATIONERY = "stationery"
    VEHICLE = "vehicle"
    BUILDING = "building"


class AssetCondition(str, enum.Enum):
    NEW = "new"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    DAMAGED = "damaged"
    DISPOSED = "disposed"


class MovementType(str, enum.Enum):
    PURCHASE = "purchase"
    ISSUED = "issued"
    RETURNED = "returned"
    DAMAGED = "damaged"
    DISPOSED = "disposed"
    TRANSFERRED = "transferred"


class Asset(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "assets"
    asset_code = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(SQLEnum(AssetCategory), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(12, 2), default=0)
    total_value = Column(Numeric(12, 2), default=0)
    location = Column(String(100), nullable=True)
    condition = Column(SQLEnum(AssetCondition), default=AssetCondition.NEW)
    purchase_date_ad = Column(Date, nullable=True)
    vendor = Column(String(200), nullable=True)
    warranty_until = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    movements = relationship("StockMovement", back_populates="asset", cascade="all, delete-orphan")


class StockMovement(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "stock_movements"
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    movement_type = Column(SQLEnum(MovementType), nullable=False)
    quantity = Column(Integer, nullable=False)
    from_location = Column(String(100), nullable=True)
    to_location = Column(String(100), nullable=True)
    moved_by = Column(UUID(as_uuid=True), nullable=True)
    moved_date_ad = Column(Date, default=date.today)
    remarks = Column(Text, nullable=True)
    asset = relationship("Asset", back_populates="movements")
