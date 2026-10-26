"""Nepal School Management System - Hostel Models"""

from datetime import date
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Date,
    DateTime,
    Integer,
    ForeignKey,
    Enum as SQLEnum,
    Numeric,
    Index,
    CheckConstraint,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
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
    __table_args__ = (
        Index("idx_hostels_school_id", "school_id"),
        Index(
            "uq_hostel_name",
            "school_id",
            func.lower(func.btrim(text("name"))),
            unique=True,
        ),
    )
    name = Column(String(200), nullable=False)
    hostel_type = Column(SQLEnum(HostelType), nullable=False)
    warden_name = Column(String(200), nullable=True)
    warden_phone = Column(String(20), nullable=True)
    total_rooms = Column(Integer, default=0)
    capacity = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    address = Column(String(300))
    notes = Column(String(1000))
    rooms = relationship("Room", back_populates="hostel", lazy="raise")


class Room(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "hostel_rooms"
    __table_args__ = (
        Index("idx_hostel_rooms_school_id", "school_id"),
        Index(
            "uq_hostel_room_number",
            "school_id",
            "hostel_id",
            func.upper(func.btrim(text("room_number"))),
            unique=True,
        ),
        CheckConstraint(
            "capacity >= 0 AND occupied >= 0 AND occupied <= capacity AND monthly_fee >= 0",
            name="ck_hostel_room_values",
        ),
    )
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    room_number = Column(String(20), nullable=False)
    floor = Column(Integer, default=0)
    capacity = Column(Integer, default=2)
    occupied = Column(Integer, default=0)
    room_type = Column(SQLEnum(RoomType), default=RoomType.DOUBLE)
    monthly_fee = Column(Numeric(10, 2), default=0)
    is_active = Column(Boolean, default=True)
    notes = Column(String(1000))
    hostel = relationship("Hostel", back_populates="rooms")


class RoomAllocation(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "room_allocations"
    __table_args__ = (
        Index("idx_room_allocations_school_id", "school_id"),
        Index(
            "uq_hostel_student_active",
            "school_id",
            "student_id",
            unique=True,
            postgresql_where=text("status='ACTIVE'"),
        ),
        Index(
            "uq_hostel_bed_active",
            "bed_id",
            unique=True,
            postgresql_where=text("status='ACTIVE'"),
        ),
        Index(
            "ix_hostel_resident_register",
            "school_id",
            "status",
            "room_id",
            "allocated_date_ad",
        ),
        Index(
            "ix_hostel_student_stay_dates",
            "school_id",
            "student_id",
            "allocated_date_ad",
            "created_at",
            "id",
        ),
        CheckConstraint(
            "monthly_fee >= 0 AND (vacated_date_ad IS NULL OR vacated_date_ad >= allocated_date_ad) AND ((status='ACTIVE' AND bed_id IS NOT NULL AND vacated_date_ad IS NULL) OR (status='VACATED' AND vacated_date_ad IS NOT NULL))",
            name="ck_hostel_allocation_values",
        ),
    )
    room_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hostel_rooms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    student_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    allocated_date_ad = Column(Date, default=date.today, nullable=False)
    vacated_date_ad = Column(Date, nullable=True)
    status = Column(
        SQLEnum(AllocationStatus),
        default=AllocationStatus.ACTIVE,
        index=True,
        nullable=False,
    )
    academic_year_bs = Column(String(10), nullable=True)
    bed_id = Column(
        UUID(as_uuid=True), ForeignKey("hostel_beds.id", ondelete="RESTRICT")
    )
    student_name = Column(String(200), nullable=False)
    student_reference = Column(String(100))
    hostel_name = Column(String(200), nullable=False)
    room_number = Column(String(20), nullable=False)
    bed_label = Column(String(30))
    monthly_fee = Column(Numeric(10, 2), default=0, nullable=False)
    notes = Column(String(1000))
    checkout_reason = Column(String(1000))
    previous_allocation_id = Column(
        UUID(as_uuid=True), ForeignKey("room_allocations.id", ondelete="RESTRICT")
    )


class HostelBed(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "hostel_beds"
    __table_args__ = (
        Index("uq_hostel_bed_label", "school_id", "room_id", "label", unique=True),
        Index("ix_hostel_bed_inventory", "school_id", "room_id", "status"),
        CheckConstraint(
            "status IN ('active','maintenance','retired')", name="ck_hostel_bed_status"
        ),
    )
    room_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hostel_rooms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    label = Column(String(30), nullable=False)
    status = Column(String(20), default="active", nullable=False)
    notes = Column(String(1000))


class HostelLeave(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "hostel_leaves"
    __table_args__ = (
        Index(
            "uq_hostel_open_leave",
            "allocation_id",
            unique=True,
            postgresql_where=text("returned_at IS NULL"),
        ),
        Index(
            "ix_hostel_leave_due",
            "school_id",
            "expected_return_ad",
            postgresql_where=text("returned_at IS NULL"),
        ),
        CheckConstraint(
            "returned_at IS NULL OR returned_at >= departed_at",
            name="ck_hostel_leave_times",
        ),
    )
    allocation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("room_allocations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    departed_at = Column(DateTime(timezone=True), nullable=False)
    expected_return_ad = Column(Date, nullable=False)
    returned_at = Column(DateTime(timezone=True))
    destination = Column(String(200), nullable=False)
    responsible_person = Column(String(200), nullable=False)
    contact_phone = Column(String(20))
    reason = Column(String(1000), nullable=False)
    return_notes = Column(String(1000))


class HostelVisit(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "hostel_visits"
    allocation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("room_allocations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    visitor_name = Column(String(200), nullable=False)
    relation = Column(String(50), nullable=False)
    contact_phone = Column(String(20))
    purpose = Column(String(500), nullable=False)
    arrived_at = Column(DateTime(timezone=True), nullable=False)
    departed_at = Column(DateTime(timezone=True))
    __table_args__ = (
        Index("ix_hostel_visit_register", "school_id", "allocation_id", "arrived_at"),
        CheckConstraint(
            "departed_at IS NULL OR departed_at >= arrived_at",
            name="ck_hostel_visit_times",
        ),
    )


class HostelRegister(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "hostel_register"
    __table_args__ = (
        Index(
            "uq_hostel_register_entry",
            "school_id",
            "allocation_id",
            "date_ad",
            "session",
            unique=True,
        ),
        Index("ix_hostel_register_date", "school_id", "date_ad", "session"),
        CheckConstraint(
            "(session IN ('morning','evening') AND status IN ('present','absent','on_leave','excused')) OR (session IN ('breakfast','lunch','snacks','dinner') AND status IN ('taken','skipped'))",
            name="ck_hostel_register_status",
        ),
        CheckConstraint("version > 0", name="ck_hostel_register_version"),
    )
    allocation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("room_allocations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    date_ad = Column(Date, nullable=False)
    session = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    notes = Column(String(500))
    version = Column(Integer, nullable=False, default=1)
    recorded_by = Column(UUID(as_uuid=True), nullable=False)


class HostelCharge(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "hostel_charges"
    __table_args__ = (
        Index(
            "uq_hostel_charge_month", "school_id", "student_id", "month_bs", unique=True
        ),
    )
    allocation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("room_allocations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    student_id = Column(UUID(as_uuid=True), nullable=False)
    month_bs = Column(String(7), nullable=False)
    ledger_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fee_ledger.id", ondelete="RESTRICT"),
        nullable=False,
    )


class HostelEvent(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "hostel_events"
    __table_args__ = (
        Index("uq_hostel_request", "school_id", "request_id", unique=True),
        Index("ix_hostel_history", "school_id", "created_at"),
        Index("ix_hostel_stay_history", "school_id", "allocation_id", "created_at"),
    )
    request_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(40), nullable=False)
    allocation_id = Column(
        UUID(as_uuid=True), ForeignKey("room_allocations.id", ondelete="RESTRICT")
    )
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    actor_name = Column(String(200))
    payload = Column(JSONB, nullable=False)
    result = Column(JSONB, nullable=False)
    before_values = Column(JSONB, nullable=False, default=dict)
