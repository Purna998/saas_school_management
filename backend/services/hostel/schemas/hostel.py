"""Nepal School Management System - Hostel Schemas"""
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class HostelCreate(BaseModel):
    name: str
    hostel_type: str
    warden_name: Optional[str] = None
    warden_phone: Optional[str] = None
    total_rooms: int = 0
    capacity: int = 0


class HostelResponse(BaseModel):
    id: UUID
    name: str
    hostel_type: str
    warden_name: Optional[str] = None
    warden_phone: Optional[str] = None
    total_rooms: int
    capacity: int
    is_active: bool
    class Config:
        from_attributes = True


class RoomCreate(BaseModel):
    hostel_id: UUID
    room_number: str
    floor: int = 0
    capacity: int = 2
    room_type: str = "double"
    monthly_fee: Decimal = Field(default=0)


class RoomResponse(BaseModel):
    id: UUID
    hostel_id: UUID
    room_number: str
    floor: int
    capacity: int
    occupied: int
    room_type: str
    monthly_fee: Decimal
    is_active: bool
    class Config:
        from_attributes = True


class AllocateRequest(BaseModel):
    room_id: UUID
    student_id: UUID
    academic_year_bs: Optional[str] = None


class AllocationResponse(BaseModel):
    id: UUID
    room_id: UUID
    student_id: UUID
    allocated_date_ad: date
    vacated_date_ad: Optional[date] = None
    status: str
    academic_year_bs: Optional[str] = None
    class Config:
        from_attributes = True


class HostelStatsResponse(BaseModel):
    total_hostels: int
    total_rooms: int
    total_capacity: int
    total_occupied: int
    occupancy_rate: float
