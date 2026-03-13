from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.models.item import Item
from app.schemas.item import ItemCreate, ItemResponse, ItemUpdate

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("/next-id")
async def next_id(db: AsyncSession = Depends(get_db)):
    """Return the next available item ID (max existing + 1)."""
    result = await db.execute(select(func.max(Item.id)))
    max_id = result.scalar() or 0
    return {"next_id": max_id + 1}


@router.get("/", response_model=list[ItemResponse])
async def list_items(
    category_id: int | None = Query(None, description="Filter by category"),
    low_stock: bool = Query(False, description="Only show items below par level"),
    db: AsyncSession = Depends(get_db),
):
    """List inventory items with optional filtering.

    Args:
        category_id: Filter items by category ID (optional)
        low_stock: If True, only return items below par level (optional)
        db: Database session

    Returns:
        list[ItemResponse]: List of items matching filters
    """
    query = select(Item).options(selectinload(Item.category)).order_by(Item.name)

    if category_id is not None:
        query = query.where(Item.category_id == category_id)
    if low_stock:
        query = query.where(Item.current_quantity < Item.par_level)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate, db: AsyncSession = Depends(get_db)):
    """Create a new inventory item.

    Args:
        payload: Item data including category_id, name, unit, quantities
        db: Database session

    Returns:
        ItemResponse: Created item with generated ID and timestamps

    Raises:
        HTTPException: 400 if category_id doesn't exist, 409 if item name duplicated in category
    """
    data = payload.model_dump(exclude_none=True)
    item = Item(**data)
    db.add(item)
    try:
        await db.commit()
        await db.refresh(item, attribute_names=["category"])
    except IntegrityError as e:
        await db.rollback()
        err = str(e.orig)
        if "FOREIGN KEY" in err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category ID {payload.category_id} does not exist",
            )
        if "PRIMARY" in err or "UNIQUE" in err:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Item with ID {payload.id} already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item with name '{payload.name}' already exists in this category",
        )
    return item


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific inventory item by ID.

    Args:
        item_id: ID of the item to retrieve
        db: Database session

    Returns:
        ItemResponse: The requested item with category details

    Raises:
        HTTPException: 404 if item not found
    """
    result = await db.execute(
        select(Item).options(selectinload(Item.category)).where(Item.id == item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int, payload: ItemUpdate, db: AsyncSession = Depends(get_db)
):
    """Partially update an inventory item.

    Args:
        item_id: ID of the item to update
        payload: Partial item data (any fields can be omitted)
        db: Database session

    Returns:
        ItemResponse: Updated item with refreshed timestamps

    Raises:
        HTTPException: 404 if item not found, 400 if invalid category_id
    """
    result = await db.execute(
        select(Item).options(selectinload(Item.category)).where(Item.id == item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    try:
        await db.commit()
        await db.refresh(item)
        await db.refresh(item, attribute_names=["category"])
    except IntegrityError as e:
        await db.rollback()
        if "FOREIGN KEY" in str(e.orig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category ID does not exist",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update violates database constraints",
        )
    return item


@router.post("/{item_id}/reassign", response_model=ItemResponse)
async def reassign_item_id(
    item_id: int,
    new_id: int = Query(..., description="New ID to assign"),
    db: AsyncSession = Depends(get_db),
):
    """Change an item's primary key (QR label number)."""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    existing = await db.execute(select(Item.id).where(Item.id == new_id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item with ID {new_id} already exists",
        )

    await db.execute(
        text("UPDATE items SET id = :new_id WHERE id = :old_id"),
        {"new_id": new_id, "old_id": item_id},
    )
    await db.commit()

    result = await db.execute(
        select(Item).options(selectinload(Item.category)).where(Item.id == new_id)
    )
    return result.scalar_one()


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an inventory item.

    Args:
        item_id: ID of the item to delete
        db: Database session

    Raises:
        HTTPException: 404 if item not found
    """
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)
    await db.commit()
