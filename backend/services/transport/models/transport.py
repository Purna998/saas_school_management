"""
Nepal School Management System - Transport Models
"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    ForeignKey,
    Enum as SQLEnum,
    Numeric,
    Time,
    Date,
    DateTime,
    Index,
    CheckConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


class VehicleType(str, enum.Enum):
    BUS = "bus"
    VAN = "van"
    MICROBUS = "microbus"


class TransportType(str, enum.Enum):
    PICKUP = "pickup"
    DROP = "drop"
    BOTH = "both"


class Vehicle(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "vehicles"
    __table_args__ = (
        Index("idx_vehicles_school_id", "school_id"),
        Index(
            "uq_transport_vehicle_plate",
            "school_id",
            text("upper(regexp_replace(vehicle_number,'[[:space:]-]','','g'))"),
            unique=True,
        ),
        CheckConstraint(
            "capacity BETWEEN 1 AND 200 AND condition IN ('available','maintenance')",
            name="ck_transport_vehicle",
        ),
    )

    vehicle_number = Column(String(30), nullable=False, index=True)
    vehicle_type = Column(SQLEnum(VehicleType), nullable=False)
    capacity = Column(Integer, nullable=False)
    driver_name = Column(String(200), nullable=True)
    driver_phone = Column(String(20), nullable=True)
    driver_license = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    gps_device_id = Column(String(50), nullable=True)
    helper_name = Column(String(200))
    helper_phone = Column(String(20))
    condition = Column(String(20), nullable=False, default="available")
    insurance_expiry_ad = Column(Date)
    tax_expiry_ad = Column(Date)
    fitness_expiry_ad = Column(Date)
    permit_expiry_ad = Column(Date)
    driver_license_expiry_ad = Column(Date)
    notes = Column(String(1000))


class Route(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "routes"
    __table_args__ = (
        Index("idx_routes_school_id", "school_id"),
        Index(
            "uq_transport_route_name",
            "school_id",
            text("lower(btrim(name))"),
            unique=True,
        ),
        CheckConstraint(
            "pickup_fee >= 0 AND drop_fee >= 0 AND both_fee >= 0 AND (distance_km IS NULL OR distance_km >= 0) AND (estimated_time_minutes IS NULL OR estimated_time_minutes > 0)",
            name="ck_transport_route_values",
        ),
    )

    name = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    start_point = Column(String(200), nullable=False)
    end_point = Column(String(200), nullable=False)
    distance_km = Column(Numeric(6, 2), nullable=True)
    estimated_time_minutes = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    pickup_fee = Column(Numeric(10, 2), nullable=False, default=0)
    drop_fee = Column(Numeric(10, 2), nullable=False, default=0)
    both_fee = Column(Numeric(10, 2), nullable=False, default=0)

    stops = relationship("RouteStop", back_populates="route", lazy="raise")


class RouteStop(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "route_stops"

    __table_args__ = (
        Index(
            "uq_transport_stop_order",
            "school_id",
            "route_id",
            "stop_order",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_transport_route_stops",
            "school_id",
            "route_id",
            "is_active",
            "stop_order",
        ),
        CheckConstraint(
            "stop_order > 0 AND (latitude IS NULL OR latitude BETWEEN -90 AND 90) AND (longitude IS NULL OR longitude BETWEEN -180 AND 180) AND ((latitude IS NULL) = (longitude IS NULL)) AND (pickup_fee IS NULL OR pickup_fee >= 0) AND (drop_fee IS NULL OR drop_fee >= 0) AND (both_fee IS NULL OR both_fee >= 0)",
            name="ck_transport_stop_values",
        ),
    )
    route_id = Column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    stop_name = Column(String(200), nullable=False)
    stop_order = Column(Integer, nullable=False)
    pickup_time = Column(Time, nullable=True)
    drop_time = Column(Time, nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    pickup_fee = Column(Numeric(10, 2))
    drop_fee = Column(Numeric(10, 2))
    both_fee = Column(Numeric(10, 2))
    notes = Column(String(1000))

    route = relationship("Route", back_populates="stops")


class StudentTransport(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "student_transport"
    __table_args__ = (
        Index("idx_student_transport_school_id", "school_id"),
        Index(
            "uq_transport_student_active",
            "school_id",
            "student_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_transport_assignment_pickup", "school_id", "pickup_run_id", "is_active"
        ),
        Index("ix_transport_assignment_drop", "school_id", "drop_run_id", "is_active"),
        CheckConstraint(
            "monthly_fee >= 0 AND (end_date_ad IS NULL OR end_date_ad >= start_date_ad) AND (needs_setup OR (start_date_ad IS NOT NULL AND ((is_active AND end_date_ad IS NULL) OR (NOT is_active AND end_date_ad IS NOT NULL)) AND ((transport_type='PICKUP' AND pickup_run_id IS NOT NULL AND pickup_stop_id IS NOT NULL AND drop_run_id IS NULL AND drop_stop_id IS NULL) OR (transport_type='DROP' AND drop_run_id IS NOT NULL AND drop_stop_id IS NOT NULL AND pickup_run_id IS NULL AND pickup_stop_id IS NULL) OR (transport_type='BOTH' AND pickup_run_id IS NOT NULL AND pickup_stop_id IS NOT NULL AND drop_run_id IS NOT NULL AND drop_stop_id IS NOT NULL))))",
            name="ck_transport_assignment",
        ),
    )

    student_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False)
    stop_id = Column(UUID(as_uuid=True), ForeignKey("route_stops.id"), nullable=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True)
    transport_type = Column(
        SQLEnum(TransportType), default=TransportType.BOTH, nullable=False
    )
    monthly_fee = Column(Numeric(10, 2), default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    pickup_run_id = Column(
        UUID(as_uuid=True), ForeignKey("transport_runs.id", ondelete="RESTRICT")
    )
    drop_run_id = Column(
        UUID(as_uuid=True), ForeignKey("transport_runs.id", ondelete="RESTRICT")
    )
    pickup_stop_id = Column(
        UUID(as_uuid=True), ForeignKey("route_stops.id", ondelete="RESTRICT")
    )
    drop_stop_id = Column(
        UUID(as_uuid=True), ForeignKey("route_stops.id", ondelete="RESTRICT")
    )
    start_date_ad = Column(Date)
    end_date_ad = Column(Date)
    needs_setup = Column(Boolean, nullable=False, default=False)
    snapshot = Column(JSONB, nullable=False, default=dict)
    notes = Column(String(1000))
    end_reason = Column(String(1000))
    requires_handover = Column(Boolean, nullable=False, default=True)
    handover_contact = Column(String(200))
    handover_phone = Column(String(20))
    previous_assignment_id = Column(
        UUID(as_uuid=True), ForeignKey("student_transport.id", ondelete="RESTRICT")
    )


class TransportRun(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "transport_runs"
    __table_args__ = (
        Index(
            "uq_transport_run_name",
            "school_id",
            text("lower(btrim(name))"),
            unique=True,
        ),
        Index(
            "ix_transport_vehicle_runs",
            "school_id",
            "vehicle_id",
            "is_active",
            "start_time",
        ),
        CheckConstraint(
            "direction IN ('pickup','drop') AND end_time > start_time AND jsonb_typeof(weekdays)='array' AND jsonb_array_length(weekdays) BETWEEN 1 AND 7",
            name="ck_transport_run",
        ),
    )
    name = Column(String(200), nullable=False)
    route_id = Column(
        UUID(as_uuid=True), ForeignKey("routes.id", ondelete="RESTRICT"), nullable=False
    )
    vehicle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    direction = Column(String(10), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    weekdays = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(String(1000))


class TransportTrip(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "transport_trips"
    __table_args__ = (
        Index(
            "uq_transport_run_trip_day",
            "school_id",
            "run_id",
            "date_ad",
            unique=True,
            postgresql_where=text("status<>'cancelled'"),
        ),
        Index(
            "uq_transport_vehicle_in_progress",
            "vehicle_id",
            unique=True,
            postgresql_where=text("status='in_progress'"),
        ),
        Index("ix_transport_trip_register", "school_id", "date_ad", "status"),
        CheckConstraint(
            "status IN ('in_progress','completed','cancelled') AND (ended_at IS NULL OR ended_at >= started_at)",
            name="ck_transport_trip",
        ),
    )
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transport_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vehicle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    date_ad = Column(Date, nullable=False)
    direction = Column(String(10), nullable=False)
    snapshot = Column(JSONB, nullable=False)
    status = Column(String(20), nullable=False, default="in_progress")
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True))
    notes = Column(String(1000))
    sweep_confirmed = Column(Boolean, nullable=False, default=False)


class TransportPassenger(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "transport_passengers"
    __table_args__ = (
        Index("uq_transport_trip_student", "trip_id", "student_id", unique=True),
        Index(
            "ix_transport_passenger_assignment", "school_id", "assignment_id", "trip_id"
        ),
        CheckConstraint(
            "status IN ('pending','boarded','alighted','absent','cancelled') AND version > 0",
            name="ck_transport_passenger",
        ),
    )
    trip_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transport_trips.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assignment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_transport.id", ondelete="RESTRICT"),
        nullable=False,
    )
    student_id = Column(UUID(as_uuid=True), nullable=False)
    student_name = Column(String(200), nullable=False)
    reference = Column(String(100))
    stop_name = Column(String(200), nullable=False)
    stop_order = Column(Integer, nullable=False)
    requires_handover = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="pending")
    boarded_at = Column(DateTime(timezone=True))
    alighted_at = Column(DateTime(timezone=True))
    received_by = Column(String(200))
    notes = Column(String(1000))
    version = Column(Integer, nullable=False, default=1)


class TransportMaintenance(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "transport_maintenance"
    __table_args__ = (
        Index("ix_transport_maintenance_due", "school_id", "vehicle_id", "next_due_ad"),
        CheckConstraint(
            "cost >= 0 AND (odometer_km IS NULL OR odometer_km >= 0) AND (next_due_ad IS NULL OR next_due_ad >= service_date_ad)",
            name="ck_transport_maintenance",
        ),
    )
    vehicle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    service_date_ad = Column(Date, nullable=False)
    kind = Column(String(30), nullable=False)
    odometer_km = Column(Integer)
    cost = Column(Numeric(10, 2), nullable=False, default=0)
    next_due_ad = Column(Date)
    vendor = Column(String(200))
    notes = Column(String(1000), nullable=False)


class VehiclePosition(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "transport_positions"
    __table_args__ = (
        Index(
            "ix_transport_vehicle_position", "school_id", "vehicle_id", "recorded_at"
        ),
        CheckConstraint(
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180 AND (accuracy_m IS NULL OR accuracy_m >= 0) AND source IN ('manual','device')",
            name="ck_transport_position",
        ),
    )
    vehicle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    latitude = Column(Numeric(10, 7), nullable=False)
    longitude = Column(Numeric(10, 7), nullable=False)
    accuracy_m = Column(Numeric(10, 2))
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(10), nullable=False)


class TransportCharge(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "transport_charges"
    __table_args__ = (
        Index(
            "uq_transport_student_month",
            "school_id",
            "student_id",
            "month_bs",
            unique=True,
        ),
    )
    assignment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_transport.id", ondelete="RESTRICT"),
        nullable=False,
    )
    student_id = Column(UUID(as_uuid=True), nullable=False)
    month_bs = Column(String(7), nullable=False)
    ledger_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fee_ledger.id", ondelete="RESTRICT"),
        nullable=False,
    )


class TransportEvent(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "transport_events"
    __table_args__ = (
        Index("uq_transport_request", "school_id", "request_id", unique=True),
        Index("ix_transport_history", "school_id", "created_at"),
    )
    request_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(40), nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    actor_name = Column(String(200))
    payload = Column(JSONB, nullable=False)
    result = Column(JSONB, nullable=False)
    before_values = Column(JSONB, nullable=False, default=dict)
