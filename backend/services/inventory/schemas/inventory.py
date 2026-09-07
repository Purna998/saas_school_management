"""Nepal School Management System - Inventory Schemas"""
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class AssetCreate(BaseModel):
    asset_code: str
    name: str
    category: str
    quantity: int = Field(default=1, ge=0)
    unit_price: Decimal = Field(default=0, ge=0)
    location: Optional[str] = None
    condition: str = "new"
    purchase_date_ad: Optional[date] = None
    vendor: Optional[str] = None
    warranty_until: Optional[date] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    condition: Optional[str] = None
    is_active: Optional[bool] = None


class AssetResponse(BaseModel):
    id: UUID
    asset_code: str
    name: str
    category: str
    quantity: int
    unit_price: Decimal
    total_value: Decimal
    location: Optional[str] = None
    condition: str
    purchase_date_ad: Optional[date] = None
    vendor: Optional[str] = None
    warranty_until: Optional[date] = None
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True


class AssetListResponse(BaseModel):
    assets: List[AssetResponse]
    total: int
    page: int
    limit: int


class StockMovementCreate(BaseModel):
    asset_id: UUID
    movement_type: str
    quantity: int = Field(..., ge=1)
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    remarks: Optional[str] = None


class StockMovementResponse(BaseModel):
    id: UUID
    asset_id: UUID
    movement_type: str
    quantity: int
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    moved_date_ad: date
    remarks: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


class InventoryStatsResponse(BaseModel):
    total_assets: int
    total_value: float
    by_category: dict
    by_condition: dict
