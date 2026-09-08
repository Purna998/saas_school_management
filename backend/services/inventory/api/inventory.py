"""Nepal School Management System - Inventory API Routes"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.base import get_db
from shared.schemas.responses import success_response
from services.auth.dependencies.auth import require_permission
from services.auth.models.user import User
from services.inventory.schemas.inventory import *
from services.inventory.services.inventory_service import InventoryService

router = APIRouter()


@router.post("/assets", response_model=AssetResponse, status_code=201)
async def create_asset(data: AssetCreate, user: User = Depends(require_permission("inventory:create")), db: AsyncSession = Depends(get_db)):
    s = InventoryService(db)
    a = await s.create_asset(user.school_id, data.model_dump())
    return AssetResponse.model_validate(a)


@router.get("/assets", response_model=AssetListResponse)
async def list_assets(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), search: Optional[str] = None, category: Optional[str] = None, user: User = Depends(require_permission("inventory:read")), db: AsyncSession = Depends(get_db)):
    s = InventoryService(db)
    assets, total = await s.list_assets(user.school_id, page, limit, search, category)
    return AssetListResponse(assets=[AssetResponse.model_validate(a) for a in assets], total=total, page=page, limit=limit)


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(asset_id: uuid.UUID, user: User = Depends(require_permission("inventory:read")), db: AsyncSession = Depends(get_db)):
    s = InventoryService(db)
    return AssetResponse.model_validate(await s.get_asset(asset_id, user.school_id))


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(asset_id: uuid.UUID, data: AssetUpdate, user: User = Depends(require_permission("inventory:update")), db: AsyncSession = Depends(get_db)):
    s = InventoryService(db)
    return AssetResponse.model_validate(await s.update_asset(asset_id, data.model_dump(exclude_unset=True), user.school_id))


@router.post("/movements", response_model=StockMovementResponse, status_code=201)
async def record_movement(data: StockMovementCreate, user: User = Depends(require_permission("inventory:create")), db: AsyncSession = Depends(get_db)):
    s = InventoryService(db)
    m = await s.record_movement(user.school_id, data.model_dump(), user.id)
    return StockMovementResponse(id=m.id, asset_id=m.asset_id, movement_type=m.movement_type.value, quantity=m.quantity, from_location=m.from_location, to_location=m.to_location, moved_date_ad=m.moved_date_ad, remarks=m.remarks, created_at=m.created_at)


@router.get("/assets/{asset_id}/history", response_model=list[StockMovementResponse])
async def get_history(asset_id: uuid.UUID, user: User = Depends(require_permission("inventory:read")), db: AsyncSession = Depends(get_db)):
    s = InventoryService(db)
    movements = await s.get_asset_history(asset_id, user.school_id)
    return [StockMovementResponse(id=m.id, asset_id=m.asset_id, movement_type=m.movement_type.value, quantity=m.quantity, from_location=m.from_location, to_location=m.to_location, moved_date_ad=m.moved_date_ad, remarks=m.remarks, created_at=m.created_at) for m in movements]


@router.get("/low-stock")
async def low_stock(threshold: int = Query(5, ge=1), user: User = Depends(require_permission("inventory:read")), db: AsyncSession = Depends(get_db)):
    s = InventoryService(db)
    assets = await s.get_low_stock(user.school_id, threshold)
    return success_response(data={"assets": [{"id": str(a.id), "name": a.name, "quantity": a.quantity} for a in assets], "total": len(assets)})


@router.get("/stats", response_model=InventoryStatsResponse)
async def stats(user: User = Depends(require_permission("inventory:read")), db: AsyncSession = Depends(get_db)):
    s = InventoryService(db)
    return InventoryStatsResponse(**(await s.get_stats(user.school_id)))
