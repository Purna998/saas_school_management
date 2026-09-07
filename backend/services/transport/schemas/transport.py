"""
Nepal School Management System - Transport Schemas
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class VehicleCreate(BaseModel):
    vehicle_number: str = Field(..., max_length=30)
    vehicle_type: str
    capacity: int = Field(..., ge=1)
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    driver_license: Optional[str] = None


class VehicleResponse(BaseModel):
    id: UUID
    vehicle_number: str
    vehicle_type: str
    capacity: int
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    driver_license: Optional[str] = None
    is_active: bool
    class Config:
        from_attributes = True


class RouteStopCreate(BaseModel):
    stop_name: str
    stop_order: int
    pickup_time: Optional[str] = None
    drop_time: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RouteStopResponse(BaseModel):
    id: UUID
    stop_name: str
    stop_order: int
    pickup_time: Optional[str] = None
    drop_time: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    class Config:
        from_attributes = True


class RouteCreate(BaseModel):
    name: str
    start_point: str
    end_point: str
    description: Optional[str] = None
    distance_km: Optional[float] = None
    estimated_time_minutes: Optional[int] = None
    stops: List[RouteStopCreate] = []


class RouteResponse(BaseModel):
    id: UUID
    name: str
    start_point: str
    end_point: str
    description: Optional[str] = None
    distance_km: Optional[float] = None
    estimated_time_minutes: Optional[int] = None
    is_active: bool
    stops: List[RouteStopResponse] = []
    class Config:
        from_attributes = True


class StudentTransportAssign(BaseModel):
    student_id: UUID
    route_id: UUID
    stop_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    transport_type: str = "both"
    monthly_fee: Decimal = Field(default=0, ge=0)


class StudentTransportResponse(BaseModel):
    id: UUID
    student_id: UUID
    route_id: UUID
    stop_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    transport_type: str
    monthly_fee: Decimal
    is_active: bool
    class Config:
        from_attributes = True


class TransportSummaryResponse(BaseModel):
    total_vehicles: int
    total_routes: int
    students_using: int
