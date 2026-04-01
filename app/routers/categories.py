from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.category import Category
from app.models.item import Item
from app.schemas.category import CategoryCreate, CategoryResponse

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("/", response_model=list[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Category).order_by(Category.name)
    )
    return result.scalars().all()


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreate, db: AsyncSession = Depends(get_db)):
    """Create a new inventory category.

    Args:
        payload: Category data (name)
        db: Database session

    Returns:
        CategoryResponse: Created category with generated ID

    Raises:
        HTTPException: 409 if category name already exists
    """
    # Check for duplicate name explicitly before inserting
    existing = await db.execute(
        select(Category).where(func.lower(Category.name) == payload.name.strip().lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with name '{payload.name}' already exists",
        )
    category = Category(name=payload.name.strip())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a category by ID.

    Args:
        category_id: ID of the category to delete

    Raises:
        HTTPException: 404 if category not found
        HTTPException: 409 if category still has items
    """
    result = await db.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    item_count = await db.scalar(
        select(func.count()).select_from(Item).where(Item.category_id == category_id)
    )
    if item_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete '{category.name}' — it still has {item_count} item{'s' if item_count != 1 else ''}. Remove or reassign them first.",
        )
    await db.delete(category)
    await db.commit()
