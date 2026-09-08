"""Nepal School Management System - Hostel Service"""
import uuid
from datetime import date
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from shared.utils.exceptions import RecordNotFoundError
from services.hostel.models.hostel import Hostel, Room, RoomAllocation, HostelType, RoomType, AllocationStatus


class HostelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_hostel(self, school_id: uuid.UUID, data: dict) -> Hostel:
        hostel = Hostel(id=uuid.uuid4(), school_id=school_id, name=data["name"], hostel_type=HostelType(data["hostel_type"]), warden_name=data.get("warden_name"), warden_phone=data.get("warden_phone"), total_rooms=data.get("total_rooms", 0), capacity=data.get("capacity", 0), is_active=True)
        self.db.add(hostel)
        await self.db.commit()
        await self.db.refresh(hostel)
        return hostel

    async def list_hostels(self, school_id: uuid.UUID) -> List[Hostel]:
        result = await self.db.execute(select(Hostel).where(Hostel.school_id == school_id, Hostel.is_active == True))
        return result.scalars().all()

    async def create_room(self, school_id: uuid.UUID, data: dict) -> Room:
        room = Room(id=uuid.uuid4(), school_id=school_id, hostel_id=data["hostel_id"], room_number=data["room_number"], floor=data.get("floor", 0), capacity=data.get("capacity", 2), room_type=RoomType(data.get("room_type", "double")), monthly_fee=data.get("monthly_fee", 0), is_active=True)
        self.db.add(room)
        await self.db.commit()
        await self.db.refresh(room)
        return room

    async def list_rooms(self, school_id: uuid.UUID, hostel_id: uuid.UUID = None) -> List[Room]:
        query = select(Room).where(Room.school_id == school_id, Room.is_active == True)
        if hostel_id:
            query = query.where(Room.hostel_id == hostel_id)
        return (await self.db.execute(query)).scalars().all()

    async def allocate_student(self, school_id: uuid.UUID, data: dict) -> RoomAllocation:
        room = (await self.db.execute(select(Room).where(Room.id == data["room_id"]))).scalar_one_or_none()
        if not room:
            raise RecordNotFoundError("Room", str(data["room_id"]))
        if room.occupied >= room.capacity:
            raise ValueError("Room is at full capacity")

        allocation = RoomAllocation(id=uuid.uuid4(), school_id=school_id, room_id=data["room_id"], student_id=data["student_id"], academic_year_bs=data.get("academic_year_bs"), status=AllocationStatus.ACTIVE)
        room.occupied += 1
        self.db.add(allocation)
        await self.db.commit()
        await self.db.refresh(allocation)
        return allocation

    async def vacate_student(self, allocation_id: uuid.UUID):
        allocation = (await self.db.execute(select(RoomAllocation).where(RoomAllocation.id == allocation_id))).scalar_one_or_none()
        if not allocation:
            raise RecordNotFoundError("Allocation", str(allocation_id))
        allocation.status = AllocationStatus.VACATED
        allocation.vacated_date_ad = date.today()
        room = (await self.db.execute(select(Room).where(Room.id == allocation.room_id))).scalar_one_or_none()
        if room and room.occupied > 0:
            room.occupied -= 1
        await self.db.commit()

    async def get_occupancy(self, school_id: uuid.UUID) -> dict:
        active_rooms = (Room.school_id == school_id, Room.is_active.is_(True))
        row = (
            await self.db.execute(
                select(
                    select(func.count(Hostel.id)).where(
                        Hostel.school_id == school_id,
                        Hostel.is_active.is_(True),
                    ).scalar_subquery().label("hostels"),
                    select(func.count(Room.id)).where(*active_rooms).scalar_subquery().label("rooms"),
                    select(func.sum(Room.capacity)).where(*active_rooms).scalar_subquery().label("capacity"),
                    select(func.sum(Room.occupied)).where(*active_rooms).scalar_subquery().label("occupied"),
                )
            )
        ).one()
        hostels = row.hostels or 0
        rooms = row.rooms or 0
        total_cap = row.capacity or 0
        total_occ = row.occupied or 0
        rate = (total_occ / total_cap * 100) if total_cap > 0 else 0
        return {"total_hostels": hostels, "total_rooms": rooms, "total_capacity": total_cap, "total_occupied": total_occ, "occupancy_rate": round(rate, 1)}
