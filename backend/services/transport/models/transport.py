"""
Nepal School Management System - Transport Models
"""

import uuid
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Enum as SQLEnum, Numeric, Time
from sqlalchemy.dialects.postgresql import UUID
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

    vehicle_number = Column(String(30), nullable=False, index=True)
    vehicle_type = Column(SQLEnum(VehicleType), nullable=False)
    capacity = Column(Integer, nullable=False)
    driver_name = Column(String(200), nullable=True)
    driver_phone = Column(String(20), nullable=True)
    driver_license = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    gps_device_id = Column(String(50), nullable=True)


class Route(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "routes"

    name = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    start_point = Column(String(200), nullable=False)
    end_point = Column(String(200), nullable=False)
    distance_km = Column(Numeric(6, 2), nullable=True)
    estimated_time_minutes = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    stops = relationship("RouteStop", back_populates="route", cascade="all, delete-orphan")


class RouteStop(Base, BaseModel, TimestampMixin):
    __tablename__ = "route_stops"

    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_name = Column(String(200), nullable=False)
    stop_order = Column(Integer, nullable=False)
    pickup_time = Column(Time, nullable=True)
    drop_time = Column(Time, nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)

    route = relationship("Route", back_populates="stops")


class StudentTransport(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "student_transport"

    student_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    route_id = Column(UUID(as_uuid=True), ForeignKey("routes.id"), nullable=False)
    stop_id = Column(UUID(as_uuid=True), ForeignKey("route_stops.id"), nullable=True)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True)
    transport_type = Column(SQLEnum(TransportType), default=TransportType.BOTH, nullable=False)
    monthly_fee = Column(Numeric(10, 2), default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
