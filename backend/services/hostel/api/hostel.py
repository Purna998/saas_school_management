"""Nepal School Management System - Hostel API Routes"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from services.auth.dependencies.auth import require_permission
from services.auth.models.user import User
from services.hostel.schemas.hostel import *
from services.hostel.services.hostel_service import HostelService

router = APIRouter()


@router.post("/hostels", response_model=HostelResponse, status_code=201)
async def create_hostel(data: HostelCreate, user: User = Depends(require_permission("hostel:create")), db: AsyncSession = Depends(get_db)):
    s = HostelService(db)
    h = await s.create_hostel(user.school_id, data.model_dump())
    return HostelResponse(id=h.id, name=h.name, hostel_type=h.hostel_type.value, warden_name=h.warden_name, warden_phone=h.warden_phone, total_rooms=h.total_rooms, capacity=h.capacity, is_active=h.is_active)


@router.get("/hostels", response_model=list[HostelResponse])
async def list_hostels(user: User = Depends(require_permission("hostel:read")), db: AsyncSession = Depends(get_db)):
    s = HostelService(db)
    hostels = await s.list_hostels(user.school_id)
    return [HostelResponse(id=h.id, name=h.name, hostel_type=h.hostel_type.value, warden_name=h.warden_name, warden_phone=h.warden_phone, total_rooms=h.total_rooms, capacity=h.capacity, is_active=h.is_active) for h in hostels]


@router.post("/rooms", response_model=RoomResponse, status_code=201)
async def create_room(data: RoomCreate, user: User = Depends(require_permission("hostel:create")), db: AsyncSession = Depends(get_db)):
    s = HostelService(db)
    r = await s.create_room(user.school_id, data.model_dump())
    return RoomResponse(id=r.id, hostel_id=r.hostel_id, room_number=r.room_number, floor=r.floor, capacity=r.capacity, occupied=r.occupied, room_type=r.room_type.value, monthly_fee=r.monthly_fee, is_active=r.is_active)


@router.get("/rooms", response_model=list[RoomResponse])
async def list_rooms(hostel_id: uuid.UUID = None, user: User = Depends(require_permission("hostel:read")), db: AsyncSession = Depends(get_db)):
    s = HostelService(db)
    rooms = await s.list_rooms(user.school_id, hostel_id)
    return [RoomResponse(id=r.id, hostel_id=r.hostel_id, room_number=r.room_number, floor=r.floor, capacity=r.capacity, occupied=r.occupied, room_type=r.room_type.value, monthly_fee=r.monthly_fee, is_active=r.is_active) for r in rooms]


@router.post("/allocate", response_model=AllocationResponse, status_code=201)
async def allocate(data: AllocateRequest, user: User = Depends(require_permission("hostel:allocate")), db: AsyncSession = Depends(get_db)):
    try:
        s = HostelService(db)
        a = await s.allocate_student(user.school_id, data.model_dump())
        return AllocationResponse(id=a.id, room_id=a.room_id, student_id=a.student_id, allocated_date_ad=a.allocated_date_ad, vacated_date_ad=a.vacated_date_ad, status=a.status.value, academic_year_bs=a.academic_year_bs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=error_response(str(e), "ROOM_FULL"))


@router.post("/vacate/{allocation_id}")
async def vacate(allocation_id: uuid.UUID, user: User = Depends(require_permission("hostel:allocate")), db: AsyncSession = Depends(get_db)):
    s = HostelService(db)
    await s.vacate_student(allocation_id, user.school_id)
    return success_response(data={"message": "Student vacated"})


@router.get("/occupancy", response_model=HostelStatsResponse)
async def occupancy(user: User = Depends(require_permission("hostel:read")), db: AsyncSession = Depends(get_db)):
    s = HostelService(db)
    return HostelStatsResponse(**(await s.get_occupancy(user.school_id)))
