"""
Nepal School Management System - Transport API Routes
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import RecordNotFoundError
from services.auth.dependencies.auth import require_permission
from services.auth.models.user import User
from services.transport.schemas.transport import *
from services.transport.services.transport_service import TransportService

router = APIRouter()


@router.post("/vehicles", response_model=VehicleResponse, status_code=201)
async def create_vehicle(data: VehicleCreate, current_user: User = Depends(require_permission("transport:create")), db: AsyncSession = Depends(get_db)):
    service = TransportService(db)
    v = await service.create_vehicle(current_user.school_id, data.model_dump())
    return VehicleResponse(id=v.id, vehicle_number=v.vehicle_number, vehicle_type=v.vehicle_type.value, capacity=v.capacity, driver_name=v.driver_name, driver_phone=v.driver_phone, driver_license=v.driver_license, is_active=v.is_active)


@router.get("/vehicles", response_model=list[VehicleResponse])
async def list_vehicles(current_user: User = Depends(require_permission("transport:read")), db: AsyncSession = Depends(get_db)):
    service = TransportService(db)
    vehicles = await service.list_vehicles(current_user.school_id)
    return [VehicleResponse(id=v.id, vehicle_number=v.vehicle_number, vehicle_type=v.vehicle_type.value, capacity=v.capacity, driver_name=v.driver_name, driver_phone=v.driver_phone, driver_license=v.driver_license, is_active=v.is_active) for v in vehicles]


@router.post("/routes", response_model=RouteResponse, status_code=201)
async def create_route(data: RouteCreate, current_user: User = Depends(require_permission("transport:create")), db: AsyncSession = Depends(get_db)):
    service = TransportService(db)
    route = await service.create_route(current_user.school_id, data.model_dump())
    route = await service.get_route(route.id, current_user.school_id)
    return RouteResponse(id=route.id, name=route.name, start_point=route.start_point, end_point=route.end_point, description=route.description, distance_km=float(route.distance_km) if route.distance_km else None, estimated_time_minutes=route.estimated_time_minutes, is_active=route.is_active, stops=[RouteStopResponse(id=s.id, stop_name=s.stop_name, stop_order=s.stop_order, pickup_time=str(s.pickup_time) if s.pickup_time else None, drop_time=str(s.drop_time) if s.drop_time else None, latitude=float(s.latitude) if s.latitude else None, longitude=float(s.longitude) if s.longitude else None) for s in route.stops])


@router.get("/routes", response_model=list[RouteResponse])
async def list_routes(current_user: User = Depends(require_permission("transport:read")), db: AsyncSession = Depends(get_db)):
    service = TransportService(db)
    routes = await service.list_routes(current_user.school_id)
    return [RouteResponse(id=r.id, name=r.name, start_point=r.start_point, end_point=r.end_point, description=r.description, distance_km=float(r.distance_km) if r.distance_km else None, estimated_time_minutes=r.estimated_time_minutes, is_active=r.is_active, stops=[RouteStopResponse(id=s.id, stop_name=s.stop_name, stop_order=s.stop_order, pickup_time=str(s.pickup_time) if s.pickup_time else None, drop_time=str(s.drop_time) if s.drop_time else None, latitude=float(s.latitude) if s.latitude else None, longitude=float(s.longitude) if s.longitude else None) for s in r.stops]) for r in routes]


@router.get("/routes/{route_id}", response_model=RouteResponse)
async def get_route(route_id: uuid.UUID, current_user: User = Depends(require_permission("transport:read")), db: AsyncSession = Depends(get_db)):
    service = TransportService(db)
    r = await service.get_route(route_id, current_user.school_id)
    return RouteResponse(id=r.id, name=r.name, start_point=r.start_point, end_point=r.end_point, description=r.description, distance_km=float(r.distance_km) if r.distance_km else None, estimated_time_minutes=r.estimated_time_minutes, is_active=r.is_active, stops=[RouteStopResponse(id=s.id, stop_name=s.stop_name, stop_order=s.stop_order, pickup_time=str(s.pickup_time) if s.pickup_time else None, drop_time=str(s.drop_time) if s.drop_time else None, latitude=float(s.latitude) if s.latitude else None, longitude=float(s.longitude) if s.longitude else None) for s in r.stops])


@router.post("/assign", response_model=StudentTransportResponse, status_code=201)
async def assign_student(data: StudentTransportAssign, current_user: User = Depends(require_permission("transport:create")), db: AsyncSession = Depends(get_db)):
    service = TransportService(db)
    a = await service.assign_student(current_user.school_id, data.model_dump())
    return StudentTransportResponse(id=a.id, student_id=a.student_id, route_id=a.route_id, stop_id=a.stop_id, vehicle_id=a.vehicle_id, transport_type=a.transport_type.value, monthly_fee=a.monthly_fee, is_active=a.is_active)


@router.delete("/assign/{assignment_id}")
async def remove_assignment(assignment_id: uuid.UUID, current_user: User = Depends(require_permission("transport:delete")), db: AsyncSession = Depends(get_db)):
    service = TransportService(db)
    await service.remove_assignment(assignment_id, current_user.school_id)
    return success_response(data={"message": "Assignment removed"})


@router.get("/routes/{route_id}/students")
async def get_students_on_route(route_id: uuid.UUID, current_user: User = Depends(require_permission("transport:read")), db: AsyncSession = Depends(get_db)):
    service = TransportService(db)
    students = await service.get_students_on_route(route_id, current_user.school_id)
    return success_response(data={"students": [{"id": str(s.id), "student_id": str(s.student_id), "transport_type": s.transport_type.value} for s in students], "total": len(students)})


@router.get("/stats", response_model=TransportSummaryResponse)
async def get_stats(current_user: User = Depends(require_permission("transport:read")), db: AsyncSession = Depends(get_db)):
    service = TransportService(db)
    return TransportSummaryResponse(**(await service.get_summary(current_user.school_id)))
