"""Nepal School Management System - Hostel Models"""
import uuid
from datetime import date
from sqlalchemy import Column, String, Boolean, Date, Integer, ForeignKey, Enum as SQLEnum, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


class HostelType(str, enum.Enum):
    BOYS = "boys"
    GIRLS = "girls"
    MIXED = "mixed"


class RoomType(str, enum.Enum):
    SINGLE = "single"
    DOUBLE = "double"
    DORMITORY = "dormitory"


class AllocationStatus(str, enum.Enum):
    ACTIVE = "active"
    VACATED = "vacated"


class Hostel(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "hostels"
    name = Column(String(200), nullable=False)
    hostel_type = Column(SQLEnum(HostelType), nullable=False)
    warden_name = Column(String(200), nullable=True)
    warden_phone = Column(String(20), nullable=True)
    total_rooms = Column(Integer, default=0)
    capacity = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    rooms = relationship("Room", back_populates="hostel", cascade="all, delete-orphan")


class Room(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "hostel_rooms"
    hostel_id = Column(UUID(as_uuid=True), ForeignKey("hostels.id", ondelete="CASCADE"), nullable=False, index=True)
    room_number = Column(String(20), nullable=False)
    floor = Column(Integer, default=0)
    capacity = Column(Integer, default=2)
    occupied = Column(Integer, default=0)
    room_type = Column(SQLEnum(RoomType), default=RoomType.DOUBLE)
    monthly_fee = Column(Numeric(10, 2), default=0)
    is_active = Column(Boolean, default=True)
    hostel = relationship("Hostel", back_populates="rooms")


class RoomAllocation(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "room_allocations"
    room_id = Column(UUID(as_uuid=True), ForeignKey("hostel_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    allocated_date_ad = Column(Date, default=date.today)
    vacated_date_ad = Column(Date, nullable=True)
    status = Column(SQLEnum(AllocationStatus), default=AllocationStatus.ACTIVE, index=True)
    academic_year_bs = Column(String(10), nullable=True)
