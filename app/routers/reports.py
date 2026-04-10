from fastapi import APIRouter, Depends
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.category import Category
from app.models.item import Item
from app.schemas.item import LowStockItem

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/low-stock", response_model=list[LowStockItem])
async def low_stock_report(db: AsyncSession = Depends(get_db)):
    """Get items at or below 99% of par level with status categorization.

    Returns items needing restock, categorized by urgency:
    - critical: current_quantity <= 50% of par_level
    - low: current_quantity <= 99% of par_level (and > 50%)
    - (items above 99% of par level are excluded)

    Args:
        db: Database session

    Returns:
        list[LowStockItem]: Items sorted by status (critical first) then name
    """
    status_expr = case(
        (Item.current_quantity <= Item.par_level * 0.5, "critical"),
        (Item.current_quantity <= Item.par_level * 0.99, "low"),
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
        .where(Item.current_quantity <= Item.par_level * 0.99)
        .order_by(status_expr, Item.name)
    )

    result = await db.execute(query)
    return result.mappings().all()
