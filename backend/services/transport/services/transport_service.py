"""
Nepal School Management System - Transport Service
"""

import uuid
import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from shared.utils.exceptions import RecordNotFoundError
from services.transport.models.transport import Vehicle, Route, RouteStop, StudentTransport, VehicleType, TransportType

logger = logging.getLogger(__name__)


class TransportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_vehicle(self, school_id: uuid.UUID, data: dict) -> Vehicle:
        vehicle = Vehicle(
            id=uuid.uuid4(), school_id=school_id,
            vehicle_number=data["vehicle_number"],
            vehicle_type=VehicleType(data["vehicle_type"]),
            capacity=data["capacity"],
            driver_name=data.get("driver_name"),
            driver_phone=data.get("driver_phone"),
            driver_license=data.get("driver_license"),
            is_active=True,
        )
        self.db.add(vehicle)
        await self.db.commit()
        await self.db.refresh(vehicle)
        return vehicle

    async def list_vehicles(self, school_id: uuid.UUID) -> List[Vehicle]:
        result = await self.db.execute(
            select(Vehicle).where(Vehicle.school_id == school_id, Vehicle.is_active == True)
        )
        return result.scalars().all()

    async def create_route(self, school_id: uuid.UUID, data: dict) -> Route:
        route = Route(
            id=uuid.uuid4(), school_id=school_id,
            name=data["name"], start_point=data["start_point"], end_point=data["end_point"],
            description=data.get("description"), distance_km=data.get("distance_km"),
            estimated_time_minutes=data.get("estimated_time_minutes"), is_active=True,
        )
        self.db.add(route)
        await self.db.flush()

        for stop_data in data.get("stops", []):
            stop = RouteStop(
                id=uuid.uuid4(), route_id=route.id,
                stop_name=stop_data["stop_name"], stop_order=stop_data["stop_order"],
                pickup_time=stop_data.get("pickup_time"), drop_time=stop_data.get("drop_time"),
                latitude=stop_data.get("latitude"), longitude=stop_data.get("longitude"),
            )
            self.db.add(stop)

        await self.db.commit()
        await self.db.refresh(route)
        return route

    async def get_route(self, route_id: uuid.UUID) -> Route:
        result = await self.db.execute(
            select(Route).where(Route.id == route_id).options(selectinload(Route.stops))
        )
        route = result.scalar_one_or_none()
        if not route:
            raise RecordNotFoundError("Route", str(route_id))
        return route

    async def list_routes(self, school_id: uuid.UUID) -> List[Route]:
        result = await self.db.execute(
            select(Route).where(Route.school_id == school_id, Route.is_active == True)
            .options(selectinload(Route.stops))
        )
        return result.scalars().all()

    async def assign_student(self, school_id: uuid.UUID, data: dict) -> StudentTransport:
        assignment = StudentTransport(
            id=uuid.uuid4(), school_id=school_id,
            student_id=data["student_id"], route_id=data["route_id"],
            stop_id=data.get("stop_id"), vehicle_id=data.get("vehicle_id"),
            transport_type=TransportType(data.get("transport_type", "both")),
            monthly_fee=data.get("monthly_fee", 0), is_active=True,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def remove_assignment(self, assignment_id: uuid.UUID):
        result = await self.db.execute(select(StudentTransport).where(StudentTransport.id == assignment_id))
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise RecordNotFoundError("StudentTransport", str(assignment_id))
        assignment.is_active = False
        await self.db.commit()

    async def get_students_on_route(self, route_id: uuid.UUID) -> List[StudentTransport]:
        result = await self.db.execute(
            select(StudentTransport).where(StudentTransport.route_id == route_id, StudentTransport.is_active == True)
        )
        return result.scalars().all()

    async def get_summary(self, school_id: uuid.UUID) -> dict:
        row = (
            await self.db.execute(
                select(
                    select(func.count(Vehicle.id)).where(
                        Vehicle.school_id == school_id,
                        Vehicle.is_active.is_(True),
                    ).scalar_subquery().label("vehicles"),
                    select(func.count(Route.id)).where(
                        Route.school_id == school_id,
                        Route.is_active.is_(True),
                    ).scalar_subquery().label("routes"),
                    select(func.count(StudentTransport.id)).where(
                        StudentTransport.school_id == school_id,
                        StudentTransport.is_active.is_(True),
                    ).scalar_subquery().label("students"),
                )
            )
        ).one()
        return {
            "total_vehicles": row.vehicles or 0,
            "total_routes": row.routes or 0,
            "students_using": row.students or 0,
        }
