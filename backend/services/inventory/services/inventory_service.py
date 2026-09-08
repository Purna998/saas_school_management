"""Nepal School Management System - Inventory Service"""
import uuid
from typing import Optional, List, Tuple
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from shared.utils.exceptions import RecordNotFoundError
from services.inventory.models.inventory import Asset, StockMovement, AssetCategory, AssetCondition, MovementType


class InventoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_asset(self, school_id: uuid.UUID, data: dict) -> Asset:
        asset = Asset(
            id=uuid.uuid4(), school_id=school_id, asset_code=data["asset_code"],
            name=data["name"], category=AssetCategory(data["category"]),
            quantity=data.get("quantity", 1), unit_price=data.get("unit_price", 0),
            total_value=data.get("quantity", 1) * data.get("unit_price", 0),
            location=data.get("location"), condition=AssetCondition(data.get("condition", "new")),
            purchase_date_ad=data.get("purchase_date_ad"), vendor=data.get("vendor"),
            warranty_until=data.get("warranty_until"), is_active=True,
        )
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def get_asset(self, asset_id: uuid.UUID, school_id: uuid.UUID) -> Asset:
        result = await self.db.execute(select(Asset).where(Asset.id == asset_id, Asset.school_id == school_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise RecordNotFoundError("Asset", str(asset_id))
        return asset

    async def update_asset(self, asset_id: uuid.UUID, data: dict, school_id: uuid.UUID) -> Asset:
        asset = await self.get_asset(asset_id, school_id)
        for k, v in data.items():
            if v is not None and hasattr(asset, k):
                if k == "condition":
                    setattr(asset, k, AssetCondition(v))
                else:
                    setattr(asset, k, v)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def list_assets(self, school_id: uuid.UUID, page: int = 1, limit: int = 20, search: Optional[str] = None, category: Optional[str] = None) -> Tuple[List[Asset], int]:
        query = select(Asset).where(Asset.school_id == school_id, Asset.is_active == True)
        if search:
            p = f"%{search}%"
            query = query.where((Asset.name.ilike(p)) | (Asset.asset_code.ilike(p)))
        if category:
            query = query.where(Asset.category == AssetCategory(category))
        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar()
        query = query.offset((page - 1) * limit).limit(limit).order_by(Asset.name)
        assets = (await self.db.execute(query)).scalars().all()
        return assets, total

    async def record_movement(self, school_id: uuid.UUID, data: dict, moved_by: uuid.UUID) -> StockMovement:
        asset = await self.get_asset(data["asset_id"], school_id)
        mt = MovementType(data["movement_type"])
        qty = data["quantity"]

        if mt in (MovementType.PURCHASE, MovementType.RETURNED):
            asset.quantity += qty
        elif mt in (MovementType.ISSUED, MovementType.DAMAGED, MovementType.DISPOSED):
            asset.quantity = max(0, asset.quantity - qty)
        asset.total_value = asset.quantity * asset.unit_price

        if data.get("to_location"):
            asset.location = data["to_location"]

        movement = StockMovement(
            id=uuid.uuid4(), school_id=school_id, asset_id=data["asset_id"],
            movement_type=mt, quantity=qty,
            from_location=data.get("from_location"), to_location=data.get("to_location"),
            moved_by=moved_by, remarks=data.get("remarks"),
        )
        self.db.add(movement)
        await self.db.commit()
        await self.db.refresh(movement)
        return movement

    async def get_asset_history(self, asset_id: uuid.UUID, school_id: uuid.UUID) -> List[StockMovement]:
        result = await self.db.execute(select(StockMovement).where(StockMovement.asset_id == asset_id, StockMovement.school_id == school_id).order_by(StockMovement.moved_date_ad.desc()))
        return result.scalars().all()

    async def get_low_stock(self, school_id: uuid.UUID, threshold: int = 5) -> List[Asset]:
        result = await self.db.execute(select(Asset).where(Asset.school_id == school_id, Asset.is_active == True, Asset.quantity <= threshold).order_by(Asset.quantity))
        return result.scalars().all()

    async def get_stats(self, school_id: uuid.UUID) -> dict:
        totals = (await self.db.execute(select(func.count(Asset.id), func.sum(Asset.total_value)).where(Asset.school_id == school_id, Asset.is_active == True))).one()
        total = totals[0] or 0
        total_val = totals[1] or 0
        cat_q = await self.db.execute(select(Asset.category, func.count()).where(Asset.school_id == school_id, Asset.is_active == True).group_by(Asset.category))
        cond_q = await self.db.execute(select(Asset.condition, func.count()).where(Asset.school_id == school_id, Asset.is_active == True).group_by(Asset.condition))
        return {"total_assets": total, "total_value": float(total_val), "by_category": {r[0].value: r[1] for r in cat_q.all()}, "by_condition": {r[0].value: r[1] for r in cond_q.all()}}
