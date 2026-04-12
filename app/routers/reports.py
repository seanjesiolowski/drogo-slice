from fastapi import APIRouter, Depends
from sqlalchemy import Float, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.category import Category
from app.models.item import Item
from app.models.storage_class import StorageClass
from app.schemas.item import LowStockItem

router = APIRouter(prefix="/api/reports", tags=["reports"])

_DEFAULT_LOW = 0.99
_DEFAULT_CRITICAL = 0.5


@router.get("/low-stock", response_model=list[LowStockItem])
async def low_stock_report(db: AsyncSession = Depends(get_db)):
    """Get items at or below their effective low threshold with status categorization.

    Each item's thresholds come from its StorageClass when assigned,
    otherwise falls back to project defaults (low=0.99, critical=0.5).

    Returns items needing restock, categorized by urgency:
    - critical: current_quantity <= critical_threshold * par_level
    - low: current_quantity <= low_threshold * par_level (and above critical)

    Returns:
        list[LowStockItem]: Items sorted by status (critical first) then name
    """
    low_t = func.coalesce(StorageClass.low_threshold, literal(_DEFAULT_LOW, Float))
    critical_t = func.coalesce(StorageClass.critical_threshold, literal(_DEFAULT_CRITICAL, Float))

    status_expr = case(
        (Item.current_quantity <= Item.par_level * critical_t, "critical"),
        (Item.current_quantity <= Item.par_level * low_t, "low"),
        else_="ok",
    )

    query = (
        select(
            Item.id,
            Item.name,
            Item.unit,
            Item.current_quantity,
            Item.par_level,
            Category.name.label("category_name"),
            status_expr.label("status"),
        )
        .join(Category, Item.category_id == Category.id)
        .outerjoin(StorageClass, Item.storage_class_id == StorageClass.id)
        .where(Item.current_quantity <= Item.par_level * low_t)
        .order_by(status_expr, Item.name)
    )

    result = await db.execute(query)
    return result.mappings().all()
